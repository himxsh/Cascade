"""Orchestrate Act + write-back (dry-run safe without GitHub/DataHub secrets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cascade.comment import build_pr_comment
from cascade.datahub_write import mark_migrated, write_dataset_breaking, write_ml_retrain
from cascade.github_act import (
    open_or_update_downstream_pr,
    owner_urns_to_reviewers,
    post_pr_comment,
)


def remediations_to_files(remediations: list[dict[str, Any]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for rem in remediations:
        sql = rem.get("rewritten_sql")
        path = rem.get("path")
        if sql and path:
            files[path] = sql
    return files


def reviewers_from_report(report: dict[str, Any]) -> list[str]:
    owners: list[str] = []
    for node in report.get("downstream") or []:
        owners.extend(node.get("owners") or [])
    return owner_urns_to_reviewers(owners)


def run_apply(
    report: dict[str, Any],
    *,
    out_dir: str | Path,
    mark_lifecycle: bool = False,
    pr_number: int | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = remediations_to_files(report.get("remediations") or [])
    reviewers = reviewers_from_report(report)
    source_urn = report.get("source_urn", "")

    # Draft comment first (no remediation URL yet) for the downstream PR body.
    draft_comment = build_pr_comment(report)
    downstream_result = open_or_update_downstream_pr(
        files,
        title="Cascade: remediate downstream schema break",
        body=draft_comment,
        out_dir=out,
        reviewers=reviewers,
        upstream_pr=pr_number,
        source_urn=source_urn or None,
    )

    remediation_url = downstream_result.get("url") if not downstream_result.get("dry_run") else None
    comment = build_pr_comment(report, remediation_pr_url=remediation_url)
    comment_result = post_pr_comment(comment, pr_number=pr_number, out_dir=out)

    plan_doc = comment
    dh_result = write_dataset_breaking(source_urn, plan_doc=plan_doc, out_dir=out)

    ml_results = []
    for m in report.get("ml_impact") or []:
        ml_results.append(
            write_ml_retrain(
                m["model_urn"],
                via_feature=m.get("via_feature", ""),
                out_dir=out,
            )
        )

    migrated_result = None
    if mark_lifecycle:
        migrated_result = mark_migrated(source_urn, out_dir=out)

    summary = {
        "out_dir": str(out),
        "comment": comment_result,
        "downstream_pr": downstream_result,
        "datahub_writeback": dh_result,
        "ml_writeback": ml_results,
        "migrated": migrated_result,
    }
    (out / "apply_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
