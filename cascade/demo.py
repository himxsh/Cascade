"""Seeded end-to-end demo: impact → generate → apply (fixture path)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cascade.agent import choose_and_rewrite
from cascade.apply import run_apply
from cascade.datahub_live import resolve_catalog
from cascade.diff_parser import load_changes
from cascade.impact import build_impact_report

DEFAULT_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"
_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIFF = str(_ROOT / "examples" / "diffs" / "raw_orders_rename_user_id.json")
DEFAULT_MODELS = str(_ROOT / "examples" / "models")

def run_demo(
    *,
    out_dir: str | Path = "artifacts/demo",
    urn: str = DEFAULT_URN,
    diff: str = DEFAULT_DIFF,
    models_dir: str = DEFAULT_MODELS,
    fixture: str | None = None,
    source: str = "fixture",
    mark_migrated: bool = True,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    gen_dir = out / "generate"
    apply_dir = out / "apply"
    gen_dir.mkdir(parents=True, exist_ok=True)

    changes = load_changes(diff)
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

    for rem in remediations:
        rewritten = rem.get("rewritten_sql")
        if rewritten and rem.get("path"):
            (gen_dir / Path(rem["path"]).name).write_text(rewritten)
    (gen_dir / "impact_report.json").write_text(json.dumps(report_dict, indent=2) + "\n")

    summary = run_apply(
        report_dict,
        out_dir=apply_dir,
        mark_lifecycle=mark_migrated,
    )
    result = {
        "urn": urn,
        "diff": diff,
        "generate_dir": str(gen_dir),
        "apply_dir": str(apply_dir),
        "severity": report_dict.get("severity"),
        "remediation_count": len(remediations),
        "apply": summary,
    }
    (out / "demo_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
