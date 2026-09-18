"""GitHub webhook HMAC + event filtering. Does not post comments (Phase 7)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from api.settings import webhook_secret

log = logging.getLogger("cascade.webhook")

REMEDIATION_PREFIX = "cascade/remediation/"
STACK_COMMAND = "/cascade stack"
PR_ACTIONS = frozenset({"opened", "synchronize", "reopened", "ready_for_review", "edited"})


class WebhookError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.message = message
        self.status = status


def verify_signature(raw_body: bytes, signature_header: str | None, secret: str | None = None) -> None:
    key = secret if secret is not None else webhook_secret()
    if not key:
        raise WebhookError("GITHUB_WEBHOOK_SECRET is not set", status=503)
    header = (signature_header or "").strip()
    if not header.startswith("sha256="):
        raise WebhookError("invalid signature", status=401)
    digest = hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()
    expected = "sha256=" + digest
    if not hmac.compare_digest(expected, header):
        raise WebhookError("invalid signature", status=401)


def parse_json_body(raw_body: bytes) -> dict[str, Any]:
    if not raw_body:
        return {}
    try:
        payload = json.loads(raw_body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise WebhookError("invalid json body", status=400) from e
    if not isinstance(payload, dict):
        raise WebhookError("webhook payload must be an object", status=400)
    return payload


def repo_fields(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None, int | None]:
    repo = payload.get("repository") or {}
    owner = str((repo.get("owner") or {}).get("login") or "")
    name = str(repo.get("name") or "")
    full = str(repo.get("full_name") or "") or (f"{owner}/{name}" if owner and name else None)
    gh_id = repo.get("id")
    github_repo_id = int(gh_id) if isinstance(gh_id, int) else None
    return full, (owner or None), (name or None), github_repo_id


def decide_event(
    event: str,
    payload: dict[str, Any],
    *,
    repo_enabled: bool | None,
) -> dict[str, Any]:
    """Return status/reason for a verified webhook. Never raises for skip cases."""
    action = payload.get("action")
    action_s = str(action) if action is not None else None
    full_name, owner, name, github_repo_id = repo_fields(payload)
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")
    base: dict[str, Any] = {
        "event": event,
        "action": action_s,
        "repo": full_name,
        "owner": owner,
        "name": name,
        "github_repo_id": github_repo_id,
        "installation_id": int(installation_id) if isinstance(installation_id, int) else None,
        "ref": None,
        "stack_requested": False,
        "queued": False,
        "status": "skipped",
        "reason": None,
    }

    if event == "ping":
        base["status"] = "pong"
        base["reason"] = "ping"
        return base

    if event not in {"pull_request", "issue_comment"}:
        base["reason"] = "ignored_event"
        return base

    if repo_enabled is None:
        base["reason"] = "unknown_repo"
        return base
    if not repo_enabled:
        base["reason"] = "disabled_repo"
        return base

    if event == "pull_request":
        pr = payload.get("pull_request") or {}
        ref = str((pr.get("head") or {}).get("ref") or "")
        base["ref"] = ref or None
        if ref.startswith(REMEDIATION_PREFIX):
            base["reason"] = "remediation_branch"
            return base
        if action_s not in PR_ACTIONS:
            base["reason"] = "ignored_action"
            return base
        base["status"] = "accepted"
        base["queued"] = True
        return base

    if event == "issue_comment":
        issue = payload.get("issue") or {}
        if not issue.get("pull_request"):
            base["reason"] = "not_a_pull_request"
            return base
        body = str((payload.get("comment") or {}).get("body") or "")
        if not body.lstrip().startswith(STACK_COMMAND):
            base["reason"] = "not_stack_command"
            return base
        base["stack_requested"] = True
        pr_ref = str((issue.get("pull_request") or {}).get("url") or "")
        base["ref"] = pr_ref or None
        base["status"] = "accepted"
        base["queued"] = True
        return base

    base["reason"] = "ignored_event"
    return base


def log_decision(decision: dict[str, Any], *, delivery_id: str) -> None:
    record = {
        "delivery_id": delivery_id,
        "event": decision.get("event"),
        "action": decision.get("action"),
        "repo": decision.get("repo"),
        "status": decision.get("status"),
        "reason": decision.get("reason"),
        "queued": decision.get("queued"),
        "stack_requested": decision.get("stack_requested"),
        "ref": decision.get("ref"),
        "installation_id": decision.get("installation_id"),
        "comment": False,
    }
    log.info("%s", json.dumps(record, sort_keys=True))
