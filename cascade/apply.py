"""Orchestrate Act + write-back (dry-run safe without GitHub/DataHub secrets)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cascade.audit import make_run_id, write_github_step_summary, write_run_audit
from cascade.comment import build_pr_comment, build_remediation_pr_body, build_remediation_title
from cascade.datahub_write import mark_migrated, write_dataset_breaking, write_ml_retrain
from cascade.github_act import (
    open_or_update_downstream_pr,
    owner_urns_to_reviewers,
    post_pr_comment,
)
from cascade.policy import evaluate_policy


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
    mode: str = "dry-run",
    audit_root: str | Path | None = None,
) -> dict[str, Any]:
    if mode not in ("dry-run", "apply"):
        raise ValueError(f"mode must be dry-run|apply, got {mode!r}")
    force_dry = mode == "dry-run"

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = remediations_to_files(report.get("remediations") or [])
    reviewers = reviewers_from_report(report)
    source_urn = report.get("source_urn", "")

    title = build_remediation_title(report)
    pr_body = build_remediation_pr_body(report)
    downstream_result = open_or_update_downstream_pr(
        files,
        title=title,
        body=pr_body,
        out_dir=out,
        reviewers=reviewers,
        upstream_pr=pr_number,
        source_urn=source_urn or None,
        force_dry_run=force_dry,
    )

    remediation_url = downstream_result.get("url") if not downstream_result.get("dry_run") else None
    remediation_open = bool(remediation_url) or bool(downstream_result.get("opened"))
    comment = build_pr_comment(report, remediation_pr_url=remediation_url)
    comment_result = post_pr_comment(
        comment,
        pr_number=pr_number,
        out_dir=out,
        force_dry_run=force_dry,
    )

    plan_doc = comment
    dh_result = write_dataset_breaking(
        source_urn,
        plan_doc=plan_doc,
        out_dir=out,
        dry_run=True if force_dry else None,
    )

    ml_results = []
    for m in report.get("ml_impact") or []:
        ml_results.append(
            write_ml_retrain(
                m["model_urn"],
                via_feature=m.get("via_feature", ""),
                out_dir=out,
                dry_run=True if force_dry else None,
            )
        )

    migrated_result = None
    if mark_lifecycle:
        migrated_result = mark_migrated(
            source_urn,
            out_dir=out,
            dry_run=True if force_dry else None,
        )

    policy = evaluate_policy(report, remediation_open=remediation_open)

    summary: dict[str, Any] = {
        "out_dir": str(out),
        "mode": mode,
        "comment": comment_result,
        "downstream_pr": downstream_result,
        "datahub_writeback": dh_result,
        "ml_writeback": ml_results,
        "migrated": migrated_result,
        "policy": policy,
    }
    (out / "apply_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    run_id = make_run_id(pr_number=pr_number)
    run_dir = write_run_audit(
        run_id=run_id,
        report=report,
        summary=summary,
        apply_out=out,
        root=audit_root,
    )
    summary["run_id"] = run_id
    summary["run_dir"] = str(run_dir)
    (out / "apply_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (run_dir / "apply_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    write_github_step_summary(summary, report)
    return summary
