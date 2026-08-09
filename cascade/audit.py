"""Run audit directory under cascade/runs/<id>/."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def make_run_id(*, pr_number: int | None = None) -> str:
    explicit = os.environ.get("CASCADE_RUN_ID", "").strip()
    if explicit:
        return explicit
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if pr_number and pr_number > 0:
        return f"pr-{pr_number}-{stamp}"
    return stamp


def write_run_audit(
    *,
    run_id: str,
    report: dict[str, Any],
    summary: dict[str, Any],
    apply_out: str | Path,
    root: str | Path | None = None,
) -> Path:
    """Copy key apply artifacts into cascade/runs/<id>/ for operator audit."""
    base = Path(root) if root is not None else Path.cwd()
    run_dir = base / "cascade" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "impact_report.json").write_text(json.dumps(report, indent=2) + "\n")
    (run_dir / "apply_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    src = Path(apply_out)
    for name in (
        "pr_comment.md",
        "downstream_pr.json",
        "downstream_pr.md",
        "downstream_pr.diff",
        "datahub_writeback.json",
        "ml_writeback.json",
        "migrated.json",
    ):
        path = src / name
        if path.is_file():
            shutil.copy2(path, run_dir / name)

    rewritten = src / "rewritten"
    if rewritten.is_dir():
        dest = run_dir / "rewritten"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(rewritten, dest)

    return run_dir


def write_github_step_summary(summary: dict[str, Any], report: dict[str, Any]) -> Path | None:
    """Append a short markdown summary when running in GitHub Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return None
    downstream = summary.get("downstream_pr") or {}
    comment = summary.get("comment") or {}
    policy = summary.get("policy") or {}
    lines = [
        "## Cascade",
        "",
        f"- **Source:** `{report.get('source_urn', '')}`",
        f"- **Severity:** `{report.get('severity', '')}`",
        f"- **Mode:** `{summary.get('mode', '')}`",
        f"- **Remediation PR:** {downstream.get('url') or '(dry-run / none)'}",
        f"- **Comment:** {'updated' if comment.get('updated') else 'posted' if comment.get('posted') else 'dry-run'}",
        f"- **Policy:** `{policy.get('code', '')}` — {policy.get('message', '')}",
        "",
    ]
    p = Path(path)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return p
