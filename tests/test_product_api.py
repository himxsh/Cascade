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
except ImportError:  # pragma: no cover
    TestClient = None  # type: ignore[misc, assignment]


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
        from api.db import reset_bootstrap_cache

        reset_bootstrap_cache()
        from api.server import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.env.stop()
        from api.db import reset_bootstrap_cache

        reset_bootstrap_cache()
        self.tmp.cleanup()

    def test_health_and_demo_diff(self) -> None:
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        body = health.json()
        self.assertTrue(body["ok"])
        self.assertIn("gms", body)
        self.assertTrue(body["db"])
        demo = self.client.get("/api/demo-diff")
        self.assertEqual(demo.status_code, 200)
        self.assertIn("diff", demo.json())

    def test_run_rejects_bad_diff(self) -> None:
        res = self.client.post("/api/run", json={"diff": "{not-json"})
        self.assertIn(res.status_code, {400, 502})

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
