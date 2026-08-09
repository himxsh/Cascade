"""DataHub write-back — dry-run by default; live GMS behind CASCADE_WRITEBACK=1.

Live path soft-imports acryl-datahub and emits real aspects (globalTags,
editableDatasetProperties, institutionalMemory) — same emitter pattern as
demo/seed_demo_graph.py. Dry-run stays stdlib JSON artifacts.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

TAG_BREAKING_PENDING = "cascade:breaking-pending"
TAG_MIGRATED = "cascade:migrated"
TAG_RETRAIN = "cascade:retrain-suggested"

_ACTOR = "urn:li:corpuser:cascade"


def _live_enabled() -> bool:
    return os.environ.get("CASCADE_WRITEBACK", "").strip() in ("1", "true", "yes")


def _want_live(dry_run: bool | None) -> bool:
    if dry_run is True:
        return False
    if dry_run is False:
        return True
    return _live_enabled()


def _gms_url() -> str:
    return (os.environ.get("DATAHUB_GMS_URL") or "http://localhost:8080").rstrip("/")


def _tag_urn(name: str) -> str:
    return f"urn:li:tag:{name}"


def _write_artifact(out_dir: str | Path | None, name: str, payload: dict[str, Any]) -> Path | None:
    if out_dir is None:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _import_sdk():
    try:
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.emitter.rest_emitter import DatahubRestEmitter
        from datahub.metadata.schema_classes import (
            AuditStampClass,
            EditableDatasetPropertiesClass,
            GlobalTagsClass,
            InstitutionalMemoryClass,
            InstitutionalMemoryMetadataClass,
            TagAssociationClass,
            TagPropertiesClass,
        )
    except ImportError as e:
        raise RuntimeError(
            "Live DataHub write-back needs acryl-datahub. "
            "Install: pip install -e '.[writeback]'  (or pip install -r demo/requirements.txt)"
        ) from e
    return {
        "MetadataChangeProposalWrapper": MetadataChangeProposalWrapper,
        "DatahubRestEmitter": DatahubRestEmitter,
        "AuditStampClass": AuditStampClass,
        "EditableDatasetPropertiesClass": EditableDatasetPropertiesClass,
        "GlobalTagsClass": GlobalTagsClass,
        "InstitutionalMemoryClass": InstitutionalMemoryClass,
        "InstitutionalMemoryMetadataClass": InstitutionalMemoryMetadataClass,
        "TagAssociationClass": TagAssociationClass,
        "TagPropertiesClass": TagPropertiesClass,
    }


def _audit(sdk: dict[str, Any]):
    return sdk["AuditStampClass"](time=int(time.time() * 1000), actor=_ACTOR)


def aspect_plan_dataset_breaking(source_urn: str, plan_doc: str, description: str) -> list[dict[str, Any]]:
    """Intended live aspects (shape for dry-run artifacts + unit tests)."""
    return [
        {"aspectName": "tagProperties", "entityUrn": _tag_urn(TAG_BREAKING_PENDING), "name": TAG_BREAKING_PENDING},
        {
            "aspectName": "globalTags",
            "entityUrn": source_urn,
            "tags": [_tag_urn(TAG_BREAKING_PENDING)],
        },
        {
            "aspectName": "editableDatasetProperties",
            "entityUrn": source_urn,
            "description": description,
        },
        {
            "aspectName": "institutionalMemory",
            "entityUrn": source_urn,
            "title": "Cascade change plan",
            "body": plan_doc,
        },
    ]


def aspect_plan_ml_retrain(model_urn: str, body: str) -> list[dict[str, Any]]:
    return [
        {"aspectName": "tagProperties", "entityUrn": _tag_urn(TAG_RETRAIN), "name": TAG_RETRAIN},
        {
            "aspectName": "globalTags",
            "entityUrn": model_urn,
            "tags": [_tag_urn(TAG_RETRAIN)],
        },
        {
            "aspectName": "institutionalMemory",
            "entityUrn": model_urn,
            "title": "Cascade ML incident",
            "body": body,
        },
    ]


def aspect_plan_migrated(source_urn: str, description: str) -> list[dict[str, Any]]:
    # ponytail: globalTags UPSERT replaces the aspect (ceiling: other tags wiped).
    # Upgrade: GraphQL getTags → merge remove/add when multi-tag coexistence matters.
    return [
        {"aspectName": "tagProperties", "entityUrn": _tag_urn(TAG_MIGRATED), "name": TAG_MIGRATED},
        {
            "aspectName": "globalTags",
            "entityUrn": source_urn,
            "tags": [_tag_urn(TAG_MIGRATED)],
            "removed": [_tag_urn(TAG_BREAKING_PENDING)],
        },
        {
            "aspectName": "editableDatasetProperties",
            "entityUrn": source_urn,
            "description": description,
        },
    ]


def _build_mcps_from_plan(plan: list[dict[str, Any]], sdk: dict[str, Any]) -> list[Any]:
    MCP = sdk["MetadataChangeProposalWrapper"]
    stamp = _audit(sdk)
    mcps: list[Any] = []
    for item in plan:
        name = item["aspectName"]
        urn = item["entityUrn"]
        if name == "tagProperties":
            mcps.append(
                MCP(
                    entityUrn=urn,
                    aspect=sdk["TagPropertiesClass"](
                        name=item["name"],
                        description=f"Cascade lifecycle tag: {item['name']}",
                    ),
                )
            )
        elif name == "globalTags":
            mcps.append(
                MCP(
                    entityUrn=urn,
                    aspect=sdk["GlobalTagsClass"](
                        tags=[sdk["TagAssociationClass"](tag=t) for t in item["tags"]],
                    ),
                )
            )
        elif name == "editableDatasetProperties":
            mcps.append(
                MCP(
                    entityUrn=urn,
                    aspect=sdk["EditableDatasetPropertiesClass"](
                        description=item["description"],
                        created=stamp,
                        lastModified=stamp,
                    ),
                )
            )
        elif name == "institutionalMemory":
            title = item["title"]
            body = item["body"]
            url = f"https://cascade.local/docs/{quote(title, safe='')}"
            mcps.append(
                MCP(
                    entityUrn=urn,
                    aspect=sdk["InstitutionalMemoryClass"](
                        elements=[
                            sdk["InstitutionalMemoryMetadataClass"](
                                url=url,
                                description=f"{title}\n\n{body}",
                                createStamp=stamp,
                            )
                        ],
                    ),
                )
            )
        else:
            raise ValueError(f"unknown aspect plan: {name}")
    return mcps


def _emit_plan(plan: list[dict[str, Any]]) -> None:
    sdk = _import_sdk()
    emitter = sdk["DatahubRestEmitter"](
        gms_server=_gms_url(),
        token=os.environ.get("DATAHUB_TOKEN") or None,
    )
    for mcp in _build_mcps_from_plan(plan, sdk):
        emitter.emit(mcp)


def write_dataset_breaking(
    source_urn: str,
    *,
    plan_doc: str,
    out_dir: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """Tags + editable description + institutional memory change plan."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    description = f"[{now}] Cascade: breaking schema change pending remediation."
    aspects = aspect_plan_dataset_breaking(source_urn, plan_doc, description)
    live = _want_live(dry_run)
    payload = {
        "urn": source_urn,
        "actions": [
            {"op": "save_document", "title": "Cascade change plan", "body": plan_doc},
            {"op": "add_tags", "tags": [TAG_BREAKING_PENDING]},
            {"op": "update_description", "description": description},
        ],
        "aspects": aspects,
        "dry_run": not live,
    }
    _write_artifact(out_dir, "datahub_writeback.json", payload)
    if not live:
        return payload

    _emit_plan(aspects)
    payload["applied"] = True
    _write_artifact(out_dir, "datahub_writeback.json", payload)
    return payload


def write_ml_retrain(
    model_urn: str,
    *,
    via_feature: str,
    out_dir: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    body = f"Feature `{via_feature}` changed; retrain suggested for `{model_urn}`."
    aspects = aspect_plan_ml_retrain(model_urn, body)
    live = _want_live(dry_run)
    payload = {
        "urn": model_urn,
        "actions": [
            {"op": "add_tags", "tags": [TAG_RETRAIN]},
            {"op": "save_document", "title": "Cascade ML incident", "body": body},
        ],
        "aspects": aspects,
        "dry_run": not live,
    }
    _write_artifact(out_dir, "ml_writeback.json", payload)
    if not live:
        return payload

    _emit_plan(aspects)
    payload["applied"] = True
    _write_artifact(out_dir, "ml_writeback.json", payload)
    return payload


def mark_migrated(
    source_urn: str,
    *,
    out_dir: str | Path | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """On remediation merge: clear pending, add cascade:migrated, refresh description."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    description = f"[{now}] Cascade: remediation merged (cascade:migrated)."
    aspects = aspect_plan_migrated(source_urn, description)
    live = _want_live(dry_run)
    payload = {
        "urn": source_urn,
        "actions": [
            {"op": "remove_tags", "tags": [TAG_BREAKING_PENDING]},
            {"op": "add_tags", "tags": [TAG_MIGRATED]},
            {"op": "update_description", "description": description},
        ],
        "aspects": aspects,
        "dry_run": not live,
    }
    _write_artifact(out_dir, "migrated.json", payload)
    if not live:
        return payload

    _emit_plan(aspects)
    payload["applied"] = True
    _write_artifact(out_dir, "migrated.json", payload)
    return payload
