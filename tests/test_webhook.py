"""HMAC verification and webhook event filtering (no live comments)."""

from __future__ import annotations

import hashlib
import hmac
import json
import unittest

from api.webhook import WebhookError, decide_event, parse_json_body, verify_signature

SECRET = "test-webhook-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


PR_PAYLOAD = {
    "action": "opened",
    "installation": {"id": 42},
    "repository": {
        "id": 1001,
        "name": "analytics",
        "full_name": "acme/analytics",
        "owner": {"login": "acme"},
    },
    "pull_request": {"head": {"ref": "feat/rename"}},
}


class TestWebhookSignature(unittest.TestCase):
    def test_valid(self) -> None:
        body = b'{"ok":true}'
        verify_signature(body, sign(body), secret=SECRET)

    def test_invalid(self) -> None:
        with self.assertRaises(WebhookError) as ctx:
            verify_signature(b'{"ok":true}', "sha256=deadbeef", secret=SECRET)
        self.assertEqual(ctx.exception.status, 401)

    def test_missing_header(self) -> None:
        with self.assertRaises(WebhookError) as ctx:
            verify_signature(b"{}", None, secret=SECRET)
        self.assertEqual(ctx.exception.status, 401)

    def test_missing_secret(self) -> None:
        with self.assertRaises(WebhookError) as ctx:
            verify_signature(b"{}", "sha256=abc", secret="")
        self.assertEqual(ctx.exception.status, 503)

    def test_bad_json(self) -> None:
        with self.assertRaises(WebhookError) as ctx:
            parse_json_body(b"not-json")
        self.assertEqual(ctx.exception.status, 400)


class TestWebhookFilter(unittest.TestCase):
    def test_accepts_enabled_pr(self) -> None:
        decision = decide_event("pull_request", PR_PAYLOAD, repo_enabled=True)
        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["queued"])
        self.assertIsNone(decision["reason"])

    def test_skips_disabled(self) -> None:
        decision = decide_event("pull_request", PR_PAYLOAD, repo_enabled=False)
        self.assertEqual(decision["status"], "skipped")
        self.assertEqual(decision["reason"], "disabled_repo")
        self.assertFalse(decision["queued"])

    def test_skips_unknown(self) -> None:
        decision = decide_event("pull_request", PR_PAYLOAD, repo_enabled=None)
        self.assertEqual(decision["reason"], "unknown_repo")

    def test_skips_remediation_branch(self) -> None:
        payload = json.loads(json.dumps(PR_PAYLOAD))
        payload["pull_request"]["head"]["ref"] = "cascade/remediation/12"
        decision = decide_event("pull_request", payload, repo_enabled=True)
        self.assertEqual(decision["reason"], "remediation_branch")
        self.assertEqual(decision["status"], "skipped")

    def test_stack_comment(self) -> None:
        payload = {
            "action": "created",
            "repository": PR_PAYLOAD["repository"],
            "issue": {"number": 3, "pull_request": {"url": "https://api.github.com/repos/acme/analytics/pulls/3"}},
            "comment": {"body": "/cascade stack\nplease"},
        }
        decision = decide_event("issue_comment", payload, repo_enabled=True)
        self.assertEqual(decision["status"], "accepted")
        self.assertTrue(decision["stack_requested"])

    def test_non_stack_comment(self) -> None:
        payload = {
            "action": "created",
            "repository": PR_PAYLOAD["repository"],
            "issue": {"number": 3, "pull_request": {"url": "https://example"}},
            "comment": {"body": "looks good"},
        }
        decision = decide_event("issue_comment", payload, repo_enabled=True)
        self.assertEqual(decision["reason"], "not_stack_command")

    def test_ping(self) -> None:
        decision = decide_event("ping", {"zen": "keep it simple"}, repo_enabled=None)
        self.assertEqual(decision["status"], "pong")

    def test_ignored_event(self) -> None:
        decision = decide_event("push", {}, repo_enabled=True)
        self.assertEqual(decision["reason"], "ignored_event")


if __name__ == "__main__":
    unittest.main()
