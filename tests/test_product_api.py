"""HTTP surface: auth, dashboard APIs, webhooks, existing /api/health and /api/run."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from fastapi.testclient import TestClient
    from api.server import _safe_next, _static_file
    from api.server import app as SERVER_APP
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]
    SERVER_APP = None  # type: ignore[misc, assignment]
    _safe_next = None  # type: ignore[misc, assignment]
    _static_file = None  # type: ignore[misc, assignment]

from api.auth import COOKIE_NAME
from api.db import get_conn, reset_bootstrap_cache
from api.github_app import (
    GitHubAppError,
    list_accessible_installation_ids,
    make_setup_state,
    user_may_claim_installation,
)
from api.store import (
    adopt_installation,
    create_session,
    seed_mock_workspace,
    set_repo_enabled,
    upsert_user,
)


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@unittest.skipUnless(TestClient is not None, "fastapi/httpx not installed")
class TestProductApi(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "api.db")
        self.secret = "webhook-secret-for-tests"
        self.env = mock.patch.dict(
            os.environ,
            {
                "DATABASE_URL": f"sqlite:///{self.db}",
                "SESSION_SECRET": "session-secret-for-tests-32chars",
                "CASCADE_DEV_LOGIN": "1",
                "GITHUB_WEBHOOK_SECRET": self.secret,
                "GITHUB_OAUTH_CLIENT_ID": "",
                "GITHUB_OAUTH_CLIENT_SECRET": "",
                "GITHUB_APP_ID": "",
                "GITHUB_APP_PRIVATE_KEY": "",
                "GITHUB_APP_SLUG": "",
            },
            clear=False,
        )
        self.env.start()
        reset_bootstrap_cache()
        self.app = SERVER_APP
        self.client = TestClient(SERVER_APP)

    def tearDown(self) -> None:
        self.env.stop()
        reset_bootstrap_cache()
        self.tmp.cleanup()

    def test_anonymous_health_is_minimal(self) -> None:
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"ok": True})

    def test_anonymous_health_survives_db_outage(self) -> None:
        with mock.patch("api.server.get_conn", side_effect=RuntimeError("db down")):
            health = self.client.get("/api/health")
            cfg = self.client.get("/api/auth/config")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json(), {"ok": True})
        self.assertEqual(cfg.status_code, 200)
        self.assertNotIn("banner", cfg.json())

    def test_authenticated_health_includes_infra(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        body = self.client.get("/api/health").json()
        self.assertTrue(body["ok"])
        self.assertIn("gms", body)
        self.assertTrue(body["db"])

    def test_demo_diff_omits_filesystem_path(self) -> None:
        demo = self.client.get("/api/demo-diff")
        self.assertEqual(demo.status_code, 200)
        body = demo.json()
        self.assertIn("diff", body)
        self.assertNotIn("path", body)

    def test_anonymous_auth_config_is_minimal(self) -> None:
        cfg = self.client.get("/api/auth/config").json()
        self.assertFalse(cfg["oauth_configured"])
        self.assertTrue(cfg["dev_login"])
        self.assertNotIn("banner", cfg)
        self.assertNotIn("app_slug", cfg)
        self.assertNotIn("app_configured", cfg)
        blob = json.dumps(cfg)
        self.assertNotIn("GITHUB_", blob)
        self.assertNotIn("mock", blob.lower())

    def test_marketing_docs_not_swagger(self) -> None:
        self.assertIsNone(self.app.docs_url)
        self.assertIsNone(self.app.redoc_url)
        self.assertIsNone(self.app.openapi_url)
        self.assertEqual(self.client.get("/openapi.json").status_code, 404)
        self.assertEqual(self.client.get("/redoc").status_code, 404)
        self.assertEqual(self.client.get("/api/swagger").status_code, 404)
        self.assertEqual(self.client.get("/api/redoc").status_code, 404)
        self.assertEqual(self.client.get("/api/internal/openapi.json").status_code, 404)
        docs = self.client.get("/docs")
        self.assertNotIn("swagger-ui", docs.text.lower())
        self.assertNotIn("Cascade UI API", docs.text)

    def test_run_rejects_bad_diff(self) -> None:
        denied = self.client.post("/api/run", json={"diff": "{not-json"})
        self.assertEqual(denied.status_code, 401)
        self.client.get("/auth/dev-login", follow_redirects=False)
        res = self.client.post("/api/run", json={"diff": "{not-json"})
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("/var/", res.text)
        self.assertNotIn("cascade/runs", res.text)

    def test_run_requires_auth_on_vercel(self) -> None:
        with mock.patch.dict(os.environ, {"VERCEL": "1"}, clear=False):
            denied = self.client.post("/api/run", json={"diff": "{not-json"})
            self.assertEqual(denied.status_code, 401)
            self.client.get("/auth/dev-login", follow_redirects=False)
            authed = self.client.post("/api/run", json={"diff": "{not-json"})
            self.assertEqual(authed.status_code, 400)

    def test_me_unauthorized(self) -> None:
        res = self.client.get("/api/me")
        self.assertEqual(res.status_code, 401)

    def test_dev_login_dashboard_toggle(self) -> None:
        res = self.client.get("/auth/dev-login", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers["location"].endswith("/app") or "/app" in res.headers["location"])
        repos_next = self.client.get("/auth/dev-login?next=/app/repos", follow_redirects=False)
        self.assertTrue(repos_next.headers["location"].endswith("/app/repos"))
        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["login"], "dev")
        self.assertTrue(me.json()["dev"])
        self.assertIsNotNone(me.json()["banner"])
        self.assertNotIn("GITHUB_APP", me.json()["banner"] or "")
        self.assertNotIn("SESSION_SECRET", me.json()["banner"] or "")

        cfg = self.client.get("/api/auth/config")
        self.assertTrue(cfg.json()["dev_login"])
        self.assertFalse(cfg.json()["oauth_configured"])
        self.assertFalse(cfg.json()["app_configured"])

        listed = self.client.get("/api/repos")
        self.assertEqual(listed.status_code, 200)
        repos = listed.json()["repos"]
        self.assertGreaterEqual(len(repos), 1)
        self.assertTrue(listed.json()["mock"])
        repo_id = repos[0]["id"]
        self.assertFalse(repos[0]["enabled"])

        patched = self.client.patch("/api/repos", json={"id": repo_id, "enabled": True})
        self.assertEqual(patched.status_code, 200)
        self.assertTrue(patched.json()["repo"]["enabled"])

        again = self.client.get("/api/repos")
        match = next(r for r in again.json()["repos"] if r["id"] == repo_id)
        self.assertTrue(match["enabled"])

        denied = self.client.patch("/api/repos", json={"id": 999999, "enabled": True})
        self.assertEqual(denied.status_code, 404)

        setup = self.client.get("/api/github/setup?installation_id=99", follow_redirects=False)
        self.assertEqual(setup.status_code, 302)
        self.assertIn("/app/repos", setup.headers["location"])

        logout = self.client.get("/auth/logout", follow_redirects=False)
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_dev_login_disabled(self) -> None:
        with mock.patch.dict(os.environ, {"CASCADE_DEV_LOGIN": ""}, clear=False):
            res = self.client.get("/auth/dev-login", follow_redirects=False)
        self.assertEqual(res.status_code, 404)

    def test_oauth_unconfigured(self) -> None:
        res = self.client.get("/auth/github", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/signin", res.headers["location"])

    def test_setup_requires_auth(self) -> None:
        res = self.client.get("/api/github/setup?installation_id=1", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/signin", res.headers["location"])

    def test_webhook_invalid_signature(self) -> None:
        body = json.dumps({"action": "opened"}).encode()
        res = self.client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=00",
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.json()["ok"])

    def test_webhook_valid_unknown_repo_skipped(self) -> None:
        payload = {
            "action": "opened",
            "repository": {
                "id": 9,
                "name": "nope",
                "full_name": "acme/nope",
                "owner": {"login": "acme"},
            },
            "pull_request": {"head": {"ref": "feat/x"}},
        }
        body = json.dumps(payload).encode()
        res = self.client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body, self.secret),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-1",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "skipped")
        self.assertEqual(data["reason"], "unknown_repo")
        self.assertFalse(data["comment"])

        dup = self.client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body, self.secret),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-1",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(dup.json()["status"], "duplicate")

    def test_two_users_isolated_mock_workspaces(self) -> None:
        with get_conn() as conn:
            alice = upsert_user(conn, github_user_id=10, login="alice")
            bob = upsert_user(conn, github_user_id=11, login="bob")
            seed_mock_workspace(conn, int(alice["id"]))
            seed_mock_workspace(conn, int(bob["id"]))
            a_repos = conn.execute(
                """
                SELECT r.id FROM repos r
                JOIN installations i ON i.installation_id = r.installation_id
                WHERE i.installer_user_id = ?
                ORDER BY r.id
                """,
                (int(alice["id"]),),
            ).fetchall()
            set_repo_enabled(
                conn,
                user_id=int(alice["id"]),
                repo_id=int(a_repos[0]["id"]),
                enabled=True,
            )
            token_a = create_session(conn, int(alice["id"]))
            token_b = create_session(conn, int(bob["id"]))

        alice_client = TestClient(self.app)
        bob_client = TestClient(self.app)
        alice_client.cookies.set(COOKIE_NAME, token_a)
        bob_client.cookies.set(COOKIE_NAME, token_b)

        a_listed = alice_client.get("/api/repos").json()["repos"]
        b_listed = bob_client.get("/api/repos").json()["repos"]
        self.assertTrue(any(row["enabled"] for row in a_listed))
        self.assertFalse(any(row["enabled"] for row in b_listed))
        self.assertNotEqual(
            {row["installation_id"] for row in a_listed},
            {row["installation_id"] for row in b_listed},
        )
        self.assertTrue(all(int(row["installation_id"]) < 0 for row in a_listed))
        self.assertTrue(all(int(row["installation_id"]) < 0 for row in b_listed))

    def test_setup_rejects_foreign_installation(self) -> None:
        with get_conn() as conn:
            alice = upsert_user(conn, github_user_id=10, login="alice")
            bob = upsert_user(conn, github_user_id=11, login="bob")
            adopt_installation(
                conn,
                user_id=int(alice["id"]),
                installation_id=99,
                account_login="acme",
            )
            token_a = create_session(conn, int(alice["id"]))
            token_b = create_session(conn, int(bob["id"]))

        alice_client = TestClient(self.app)
        bob_client = TestClient(self.app)
        alice_client.cookies.set(COOKIE_NAME, token_a)
        bob_client.cookies.set(COOKIE_NAME, token_b)
        remote = {
            "installation_id": 99,
            "account_login": "acme",
            "account_type": "Organization",
            "account_id": 555,
        }
        with mock.patch("api.server.app_configured", return_value=True), mock.patch(
            "api.server.fetch_installation", return_value=remote
        ), mock.patch("api.server.session_github_token", return_value="gho_test"), mock.patch(
            "api.server.list_accessible_installation_ids", return_value={99}
        ):
            state = make_setup_state(bob)
            stolen = bob_client.get(
                f"/api/github/setup?installation_id=99&state={state}",
                follow_redirects=False,
            )
        self.assertEqual(stolen.status_code, 302)
        self.assertIn("installation_owned", stolen.headers["location"])

        me_a = alice_client.get("/api/me").json()
        me_b = bob_client.get("/api/me").json()
        self.assertTrue(any(row["installation_id"] == 99 for row in me_a["installations"]))
        self.assertFalse(any(row["installation_id"] == 99 for row in me_b["installations"]))

    def test_setup_requires_github_when_app_configured(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        with mock.patch("api.server.app_configured", return_value=True):
            with mock.patch(
                "api.server.fetch_installation",
                side_effect=GitHubAppError("missing", status=404),
            ):
                res = self.client.get("/api/github/setup?installation_id=99", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("installation_not_found", res.headers["location"])

    def test_setup_org_requires_membership_not_just_state(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        me = self.client.get("/api/me").json()
        remote = {
            "installation_id": 77,
            "account_login": "acme",
            "account_type": "Organization",
            "account_id": 555,
        }
        with mock.patch("api.server.app_configured", return_value=True), mock.patch(
            "api.server.fetch_installation", return_value=remote
        ):
            with mock.patch("api.server.session_github_token", return_value="gho_test"), mock.patch(
                "api.server.list_accessible_installation_ids", return_value={77}
            ):
                denied = self.client.get(
                    "/api/github/setup?installation_id=77",
                    follow_redirects=False,
                )
                self.assertIn("installation_forbidden", denied.headers["location"])
                state = make_setup_state(me)
                accepted = self.client.get(
                    f"/api/github/setup?installation_id=77&state={state}",
                    follow_redirects=False,
                )
            with mock.patch("api.server.session_github_token", return_value="gho_test"), mock.patch(
                "api.server.list_accessible_installation_ids", return_value=set()
            ):
                outsider = self.client.get(
                    f"/api/github/setup?installation_id=77&state={make_setup_state(me)}",
                    follow_redirects=False,
                )
        self.assertIn("/app/repos", accepted.headers["location"])
        self.assertIn("installation_forbidden", outsider.headers["location"])

    def test_state_alone_does_not_grant_an_installation(self) -> None:
        user = {"id": 1, "github_user_id": 10}
        org = {
            "installation_id": 77,
            "account_type": "Organization",
            "account_id": 555,
        }
        self.assertFalse(
            user_may_claim_installation(user, org, state_ok=True, accessible_ids=set())
        )
        self.assertFalse(
            user_may_claim_installation(user, org, state_ok=True, accessible_ids={88})
        )
        self.assertTrue(
            user_may_claim_installation(user, org, state_ok=True, accessible_ids={77})
        )
        self.assertFalse(
            user_may_claim_installation(user, org, state_ok=False, accessible_ids={77})
        )
        own = {"installation_id": 3, "account_type": "User", "account_id": 10}
        self.assertTrue(
            user_may_claim_installation(user, own, state_ok=False, accessible_ids=set())
        )
        other = {"installation_id": 3, "account_type": "User", "account_id": 11}
        self.assertFalse(
            user_may_claim_installation(user, other, state_ok=True, accessible_ids=set())
        )

    def test_list_accessible_installation_ids(self) -> None:
        with mock.patch(
            "api.github_app._http_json",
            return_value={"installations": [{"id": 5}, {"id": "no"}, {}]},
        ):
            self.assertEqual(list_accessible_installation_ids("gho_test"), {5})

    def test_oauth_user_cannot_squat_installation_before_app_exists(self) -> None:
        with get_conn() as conn:
            user = upsert_user(conn, github_user_id=10, login="alice")
            token = create_session(conn, int(user["id"]))
        client = TestClient(self.app)
        client.cookies.set(COOKIE_NAME, token)
        res = client.get("/api/github/setup?installation_id=99", follow_redirects=False)
        self.assertIn("app_not_configured", res.headers["location"])

    def test_hosted_dev_login_cannot_squat_installation(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        with mock.patch.dict(os.environ, {"VERCEL": "1"}, clear=False):
            res = self.client.get("/api/github/setup?installation_id=99", follow_redirects=False)
        self.assertIn("app_not_configured", res.headers["location"])

    def test_dev_login_disabled_in_production(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"VERCEL_ENV": "production", "CASCADE_DEV_LOGIN": "1"},
            clear=False,
        ):
            res = self.client.get("/auth/dev-login", follow_redirects=False)
        self.assertEqual(res.status_code, 404)

    def test_login_next_stays_on_site(self) -> None:
        self.assertEqual(_safe_next("/app/repos"), "/app/repos")
        for bad in ("https://evil.example", "//evil.example", "/\\evil.example", "/evil example"):
            self.assertEqual(_safe_next(bad), "/app")
            res = self.client.get("/auth/dev-login", params={"next": bad}, follow_redirects=False)
            self.assertTrue(res.headers["location"].startswith("/app"), res.headers["location"])
            self.assertNotIn("evil.example", res.headers["location"])

    def test_static_file_stays_in_bundle(self) -> None:
        self.assertIsNone(_static_file("../pyproject.toml"))
        self.assertIsNone(_static_file("..\\pyproject.toml"))
        self.assertIsNone(_static_file("/etc/passwd"))

    def test_webhook_enabled_repo_accepted(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        listed = self.client.get("/api/repos").json()["repos"]
        target = next(r for r in listed if r["name"] == "analytics")
        self.client.patch("/api/repos", json={"id": target["id"], "enabled": True})

        payload = {
            "action": "opened",
            "repository": {
                "id": target["github_repo_id"],
                "name": "analytics",
                "full_name": "acme/analytics",
                "owner": {"login": "acme"},
            },
            "pull_request": {"head": {"ref": "feat/rename"}},
        }
        body = json.dumps(payload).encode()
        res = self.client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body, self.secret),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-ok",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "accepted")
        self.assertTrue(data["queued"])
        self.assertFalse(data["comment"])

        rem = json.loads(body)
        rem["pull_request"]["head"]["ref"] = "cascade/remediation/1"
        rem_body = json.dumps(rem).encode()
        skipped = self.client.post(
            "/api/github/webhook",
            content=rem_body,
            headers={
                "X-Hub-Signature-256": _sign(rem_body, self.secret),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-rem",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(skipped.json()["reason"], "remediation_branch")

    def test_webhook_mock_name_does_not_match_a_real_repo_id(self) -> None:
        self.client.get("/auth/dev-login", follow_redirects=False)
        listed = self.client.get("/api/repos").json()["repos"]
        target = next(r for r in listed if r["name"] == "analytics")
        self.assertLess(int(target["github_repo_id"]), 0)
        self.client.patch("/api/repos", json={"id": target["id"], "enabled": True})
        payload = {
            "action": "opened",
            "installation": {"id": 555},
            "repository": {
                "id": 1001,
                "name": "analytics",
                "full_name": "acme/analytics",
                "owner": {"login": "acme"},
            },
            "pull_request": {"head": {"ref": "feat/rename"}},
        }
        body = json.dumps(payload).encode()
        res = self.client.post(
            "/api/github/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body, self.secret),
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "deliv-real-id",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "skipped")
        self.assertEqual(res.json()["reason"], "unknown_repo")

    def test_webhook_missing_secret(self) -> None:
        with mock.patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": ""}, clear=False):
            body = b"{}"
            res = self.client.post(
                "/api/github/webhook",
                content=body,
                headers={"X-Hub-Signature-256": _sign(body, "x"), "X-GitHub-Event": "ping"},
            )
        self.assertEqual(res.status_code, 503)


if __name__ == "__main__":
    unittest.main()
