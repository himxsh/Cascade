from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade import __version__
from cascade.workflow import render_workflow
from api import github_app
from api.server import app as SERVER_APP
from api.db import reset_bootstrap_cache
from fastapi.testclient import TestClient


class TestWorkflowRendering(unittest.TestCase):
    def test_version_is_rendered(self):
        text = render_workflow()
        self.assertIn(__version__, text)
        self.assertNotIn("__CASCADE_VERSION__", text)

    def test_setup_writes_versioned_unpinned_workflow(self):
        from cascade.setup_cmd import run_init

        with tempfile.TemporaryDirectory() as td:
            run_init(Path(td))
            text = (Path(td) / ".github/workflows/cascade.yml").read_text()
        self.assertNotIn("git+https://", text)
        self.assertIn(f"@v{__version__}", text)
        self.assertIn(f'cascade-version: "{__version__}"', text)
        self.assertIn("secrets: inherit", text)
        import yaml
        run = yaml.safe_load(Path(".github/workflows/run.yml").read_text())
        on = run.get("on", run.get(True))
        self.assertIn("workflow_call", on)
        self.assertTrue(on["workflow_call"]["inputs"]["cascade-version"]["required"])


class TestGitHubWorkflowPR(unittest.TestCase):
    def test_installation_token(self):
        with mock.patch.object(github_app, "create_app_jwt", return_value="jwt"), mock.patch.object(
            github_app, "_http_json", return_value={"token": "secret-token"}
        ) as http:
            self.assertEqual(github_app.create_installation_token(42), "secret-token")
            self.assertEqual(http.call_args.kwargs["method"], "POST")
        with mock.patch.object(github_app, "create_app_jwt", return_value="jwt"), mock.patch.object(
            github_app, "_http_json", return_value={}
        ), self.assertRaises(github_app.GitHubAppError):
            github_app.create_installation_token(42)

    def test_commits_directly_to_default_branch(self):
        calls = []

        def response(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/repos/acme/analytics"):
                return {"default_branch": "main"}
            if "contents/.github/workflows/cascade.yml?ref=" in url:
                raise github_app.GitHubAppError("missing", github_status=404)
            return {}

        with mock.patch.object(github_app, "_http_json", side_effect=response), mock.patch.object(
            github_app, "render_workflow", return_value="workflow contents"
        ):
            self.assertEqual(
                github_app.install_workflow("token", "acme/analytics"), {"status": "committed"}
            )
        writes = [kwargs for _, kwargs in calls if kwargs.get("method") in {"PUT", "POST"}]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0]["body"]["branch"], "main")
        self.assertEqual(
            base64.b64decode(writes[0]["body"]["content"]).decode(), "workflow contents"
        )

    def test_creates_branch_workflow_and_pr(self):
        calls = []

        def response(url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/repos/acme/analytics"):
                return {"default_branch": "main"}
            if "/git/ref/heads/main" in url:
                return {"object": {"sha": "abc123"}}
            if "contents/.github/workflows/cascade.yml?ref=" in url:
                raise github_app.GitHubAppError("missing", github_status=404)
            if url.endswith("/contents/.github/workflows/cascade.yml") and kwargs.get("method") == "PUT" and kwargs.get("body", {}).get("branch") != "cascade/setup":
                raise github_app.GitHubAppError("protected", github_status=403)
            if "/git/ref/heads/cascade/setup" in url:
                raise github_app.GitHubAppError("missing", github_status=404)
            if "/pulls?state=open" in url:
                return []
            return {}

        with mock.patch.object(github_app, "_http_json", side_effect=response), mock.patch.object(
            github_app, "render_workflow", return_value="workflow contents"
        ):
            self.assertEqual(github_app.install_workflow("token", "acme/analytics"), {"status": "pr_opened"})
        self.assertEqual([kwargs.get("method", "GET") for _, kwargs in calls], ["GET", "GET", "PUT", "GET", "GET", "GET", "POST", "PUT", "POST"])
        put = next(kwargs for url, kwargs in calls if kwargs.get("method") == "PUT")
        self.assertEqual(base64.b64decode(put["body"]["content"]).decode(), "workflow contents")
        pr = next(kwargs["body"] for url, kwargs in calls if url.endswith("/pulls") and kwargs.get("method") == "POST")
        self.assertIn("settings/secrets/actions/new?name=LLM_API_KEY", pr["body"])

    def test_existing_workflow_branch_or_pr_skips_writes(self):
        for target in ("workflow", "branch", "pr"):
            writes = []

            def response(url, **kwargs):
                if kwargs.get("method") in {"POST", "PUT"}:
                    writes.append(url)
                if url.endswith("/repos/acme/analytics"):
                    return {"default_branch": "main"}
                if "/git/ref/heads/main" in url:
                    return {"object": {"sha": "abc"}}
                if target == "workflow" and "/contents/.github/workflows/cascade.yml?" in url:
                    return {"name": "cascade.yml"}
                if target == "branch" and "/git/ref/heads/cascade/setup" in url:
                    return {"ref": "branch"}
                if target != "workflow" and "/contents/.github/workflows/cascade.yml?" in url:
                    raise github_app.GitHubAppError("missing", github_status=404)
                if url.endswith("/contents/.github/workflows/cascade.yml") and kwargs.get("method") == "PUT":
                    raise github_app.GitHubAppError("protected", github_status=403)
                if target == "pr" and "/pulls?state=open" in url:
                    return [{"number": 1}]
                if "/git/ref/heads/cascade/setup" in url:
                    raise github_app.GitHubAppError("missing", github_status=404)
                return []

            with mock.patch.object(github_app, "_http_json", side_effect=response):
                self.assertEqual(github_app.install_workflow("token", "acme/analytics"), {"status": "exists"})
            self.assertEqual(len(writes), 1 if target != "workflow" else 0)


@unittest.skipUnless(TestClient, "fastapi/httpx not installed")
class TestWorkflowWebhook(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / "test.db")
        self.env = mock.patch.dict(os.environ, {"CASCADE_DB_PATH": self.db, "GITHUB_WEBHOOK_SECRET": "test-secret"})
        self.env.start()
        reset_bootstrap_cache()
        self.client = TestClient(SERVER_APP)

    def tearDown(self):
        self.client.close()
        reset_bootstrap_cache()
        self.env.stop()
        self.temp.cleanup()

    def post(self, event, payload, signature=True):
        body = json.dumps(payload).encode()
        headers = {"x-github-event": event}
        if signature:
            headers["x-hub-signature-256"] = "sha256=" + hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        return self.client.post("/api/github/webhook", content=body, headers=headers)

    @mock.patch("api.server.app_configured", return_value=True)
    @mock.patch("api.server.create_installation_token", return_value="token")
    @mock.patch("api.server.install_workflow", return_value={"status": "pr_opened"})
    def test_installation_created_opens_prs(self, opened, token, configured):
        response = self.post("installation", {"action": "created", "installation": {"id": 7}, "repositories": [{"full_name": "a/one"}, {"full_name": "a/two"}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["workflow_outcomes"]), 2)
        self.assertEqual(opened.call_count, 2)

    @mock.patch("api.server.app_configured", return_value=True)
    @mock.patch("api.server.create_installation_token", return_value="token")
    @mock.patch("api.server.install_workflow", side_effect=[RuntimeError("oops"), {"status": "pr_opened"}])
    def test_added_repos_isolates_errors(self, opened, token, configured):
        response = self.post("installation_repositories", {"action": "added", "installation": {"id": 7}, "repositories_added": [{"full_name": "a/one"}, {"full_name": "a/two"}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow_outcomes"], [{"repo": "a/one", "status": "error"}, {"repo": "a/two", "status": "pr_opened"}])

    @mock.patch("api.server.app_configured", return_value=False)
    @mock.patch("api.server.install_workflow")
    def test_disabled_app_skips_pr(self, opened, configured):
        response = self.post("installation", {"action": "created", "installation": {"id": 7}, "repositories": [{"full_name": "a/one"}]})
        self.assertEqual(response.status_code, 200)
        opened.assert_not_called()

    def test_bad_signature_is_401(self):
        self.assertEqual(self.post("installation", {}, signature=False).status_code, 401)


if __name__ == "__main__":
    unittest.main()
