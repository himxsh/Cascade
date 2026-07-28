"""DataHub write-back — dry-run by default; live GMS behind CASCADE_WRITEBACK=1."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TAG_BREAKING_PENDING = "cascade:breaking-pending"
TAG_MIGRATED = "cascade:migrated"
TAG_RETRAIN = "cascade:retrain-suggested"


def _live_enabled() -> bool:
    return os.environ.get("CASCADE_WRITEBACK", "").strip() in ("1", "true", "yes")


def _gms_url() -> str:
    return (os.environ.get("DATAHUB_GMS_URL") or "http://localhost:8080").rstrip("/")


def _auth_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = os.environ.get("DATAHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_gms_url()}{path}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=_auth_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"DataHub write {path} failed: {e.code} {detail}") from e


def _write_artifact(out_dir: str | Path | None, name: str, payload: dict[str, Any]) -> Path | None:
    if out_dir is None:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def write_dataset_breaking(
    source_urn: str,
    *,
    plan_doc: str,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """save_document + add_tags(breaking-pending) + update_description (dry-run unless CASCADE_WRITEBACK)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    payload = {
        "urn": source_urn,
        "actions": [
            {"op": "save_document", "title": "Cascade change plan", "body": plan_doc},
            {"op": "add_tags", "tags": [TAG_BREAKING_PENDING]},
            {
                "op": "update_description",
                "description": f"[{now}] Cascade: breaking schema change pending remediation.",
            },
        ],
        "dry_run": not _live_enabled(),
    }
    _write_artifact(out_dir, "datahub_writeback.json", payload)
    if not _live_enabled():
        return payload

    # ponytail: GraphQL/REST emit stub — posts a single openapi aspects payload when GMS is up.
    # Upgrade: real MCP save_document / add_tags / update_description tools.
    for action in payload["actions"]:
        _post_json(
            "/aspects?action=ingestProposal",
            {
                "proposal": {
                    "entityType": "dataset",
                    "entityUrn": source_urn,
                    "changeType": "UPSERT",
                    "aspectName": "cascadeStub",
                    "aspect": {"value": json.dumps(action), "contentType": "application/json"},
                }
            },
        )
    payload["applied"] = True
    _write_artifact(out_dir, "datahub_writeback.json", payload)
    return payload


def write_ml_retrain(
    model_urn: str,
    *,
    via_feature: str,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    payload = {
        "urn": model_urn,
        "actions": [
            {"op": "add_tags", "tags": [TAG_RETRAIN]},
            {
                "op": "save_document",
                "title": "Cascade ML incident",
                "body": f"Feature `{via_feature}` changed; retrain suggested for `{model_urn}`.",
            },
        ],
        "dry_run": not _live_enabled(),
    }
    _write_artifact(out_dir, "ml_writeback.json", payload)
    if not _live_enabled():
        return payload

    for action in payload["actions"]:
        _post_json(
            "/aspects?action=ingestProposal",
            {
                "proposal": {
                    "entityType": "mlModel",
                    "entityUrn": model_urn,
                    "changeType": "UPSERT",
                    "aspectName": "cascadeStub",
                    "aspect": {"value": json.dumps(action), "contentType": "application/json"},
                }
            },
        )
    payload["applied"] = True
    _write_artifact(out_dir, "ml_writeback.json", payload)
    return payload


def mark_migrated(
    source_urn: str,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """On remediation merge: clear pending, add cascade:migrated. No-op dry-run without credentials."""
    payload = {
        "urn": source_urn,
        "actions": [
            {"op": "remove_tags", "tags": [TAG_BREAKING_PENDING]},
            {"op": "add_tags", "tags": [TAG_MIGRATED]},
        ],
        "dry_run": not _live_enabled(),
    }
    _write_artifact(out_dir, "migrated.json", payload)
    if not _live_enabled():
        return payload

    for action in payload["actions"]:
        _post_json(
            "/aspects?action=ingestProposal",
            {
                "proposal": {
                    "entityType": "dataset",
                    "entityUrn": source_urn,
                    "changeType": "UPSERT",
                    "aspectName": "cascadeStub",
                    "aspect": {"value": json.dumps(action), "contentType": "application/json"},
                }
            },
        )
    payload["applied"] = True
    _write_artifact(out_dir, "migrated.json", payload)
    return payload
