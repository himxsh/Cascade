"""UI pipeline: impact → generate → apply dry-run → UI payload."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from cascade.agent import choose_and_rewrite
from cascade.apply import run_apply
from cascade.datahub_live import resolve_catalog
from cascade.demo import DEFAULT_DIFF, DEFAULT_MODELS, DEFAULT_URN
from cascade.diff_parser import parse_changes_text
from cascade.impact import build_impact_report

STEPS = ("classify", "impact", "reason", "rewrite", "write-back")


def _short_label(urn: str) -> str:
    if "mlModel" in urn:
        # urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)
        parts = urn.split(",")
        return parts[1] if len(parts) >= 2 else urn
    if "dataset" in urn:
        parts = urn.split(",")
        if len(parts) >= 2:
            return parts[1].rstrip(")").split(".")[-1]
    return urn.rsplit(":", 1)[-1][:32]


def _build_graph(
    source_urn: str,
    report: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    rem_by_urn = {r["urn"]: r for r in report.get("remediations") or [] if r.get("urn")}
    nodes: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_node(
        urn: str,
        *,
        kind: str,
        owners: list[str] | None = None,
    ) -> None:
        if urn in seen:
            return
        seen.add(urn)
        rem = rem_by_urn.get(urn, {})
        nodes.append(
            {
                "id": urn,
                "label": _short_label(urn),
                "kind": kind,
                "owners": owners or [],
                "strategy": rem.get("strategy"),
                "rationale": rem.get("rationale"),
                "path": rem.get("path"),
            }
        )

    add_node(source_urn, kind="source", owners=catalog.get("datasets_by_urn", {}).get(source_urn, {}).get("owners", []))
    for d in report.get("downstream") or []:
        add_node(d["urn"], kind=d.get("type", "dataset"), owners=d.get("owners") or [])
    for m in report.get("ml_impact") or []:
        add_node(m["model_urn"], kind="mlModel", owners=[])

    edges: list[dict[str, str]] = []
    dm = catalog.get("downstream_map") or {}
    for src, targets in dm.items():
        if src not in seen:
            continue
        for tgt in targets:
            if tgt in seen:
                edges.append({"from": src, "to": tgt})

    for m in report.get("ml_impact") or []:
        via = m.get("via_feature")
        feature = (catalog.get("ml_features_by_name") or {}).get(via or "")
        model_urn = m.get("model_urn")
        if feature and model_urn:
            for src in feature.get("sources") or []:
                if src in seen:
                    edges.append({"from": src, "to": model_urn})

    return {"nodes": nodes, "edges": edges}


def _enrich_files(
    remediations: list[dict[str, Any]],
    models_dir: str | Path,
) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for rem in remediations:
        path = rem.get("path")
        after = rem.get("rewritten_sql")
        if not path or not after:
            continue
        p = Path(path)
        if not p.is_file():
            candidate = Path(models_dir) / Path(path).name
            p = candidate if candidate.is_file() else p
        before = p.read_text() if p.is_file() else ""
        files.append({"path": str(path), "before": before, "after": after})
    return files


def load_demo_diff() -> dict[str, Any]:
    path = Path(DEFAULT_DIFF)
    return {
        "urn": DEFAULT_URN,
        "source": "fixture",
        "diff": path.read_text(),
        "path": str(path),
    }


def run_ui_pipeline(
    *,
    diff_text: str,
    urn: str = DEFAULT_URN,
    source: str = "fixture",
    models_dir: str | Path = DEFAULT_MODELS,
    fixture: str | None = None,
    mark_migrated: bool = True,
) -> dict[str, Any]:
    """Run the Cascade loop and return a UI-ready payload (no secrets to client)."""
    changes = parse_changes_text(diff_text)
    if not changes:
        raise ValueError("No schema changes found in diff (expected JSON changes or SQL/dbt diff)")

    catalog = resolve_catalog(source, urn, fixture)
    report = build_impact_report(source_urn=urn, changes=changes, catalog=catalog)
    remediations = choose_and_rewrite(
        changes=changes,
        catalog=catalog,
        models_dir=models_dir,
        source_urn=urn,
    )
    report.remediations = remediations
    report_dict = report.to_dict()

    with tempfile.TemporaryDirectory(prefix="cascade-ui-") as tmp:
        apply_summary = run_apply(
            report_dict,
            out_dir=tmp,
            mark_lifecycle=mark_migrated,
        )
        # Inline artifact bodies so the client does not need the temp path
        apply_dir = Path(tmp)
        artifacts: dict[str, Any] = {
            "datahub_writeback": apply_summary.get("datahub_writeback"),
            "ml_writeback": apply_summary.get("ml_writeback"),
            "migrated": apply_summary.get("migrated"),
            "downstream_pr": apply_summary.get("downstream_pr"),
            "comment": apply_summary.get("comment"),
        }
        for name in (
            "pr_comment.md",
            "downstream_pr.diff",
            "datahub_writeback.json",
            "ml_writeback.json",
            "migrated.json",
        ):
            p = apply_dir / name
            if p.is_file():
                artifacts[name] = p.read_text()

    files = _enrich_files(remediations, models_dir)
    graph = _build_graph(urn, report_dict, catalog)

    return {
        "steps": list(STEPS),
        "catalog_source": source,
        "report": report_dict,
        "graph": graph,
        "files": files,
        "apply": artifacts,
    }
