"""Build GitHub PR comment markdown from an ImpactReport dict."""

from __future__ import annotations

from typing import Any


def build_pr_comment(report: dict[str, Any]) -> str:
    source = report.get("source_urn", "(unknown)")
    severity = report.get("severity", "unknown")
    changes = report.get("changes") or []
    downstream = report.get("downstream") or []
    remediations = report.get("remediations") or []
    ml_impact = report.get("ml_impact") or []

    lines: list[str] = [
        "## Cascade impact report",
        "",
        f"**Source:** `{source}`",
        f"**Severity:** `{severity}`",
        "",
        "### Schema changes",
        "",
    ]
    if not changes:
        lines.append("_No schema changes detected._")
    else:
        for c in changes:
            ctype = c.get("type", "?")
            if ctype == "FIELD_RENAMED":
                lines.append(
                    f"- `{ctype}`: `{c.get('from')}` → `{c.get('to')}`"
                    f" (detected_by={c.get('detected_by', '?')})"
                )
            elif ctype == "FIELD_REMOVED":
                lines.append(f"- `{ctype}`: `{c.get('from')}`")
            else:
                lines.append(f"- `{ctype}`: {c}")

    lines.extend(["", "### Blast radius", ""])
    if not downstream:
        lines.append("_No downstream nodes._")
    else:
        for node in downstream:
            owners = ", ".join(node.get("owners") or []) or "(none)"
            lines.append(f"- `{node.get('urn')}` — owners: {owners}")

    lines.extend(["", "### Agent remediations", ""])
    if not remediations:
        lines.append("_No remediations generated._")
    else:
        for rem in remediations:
            strategy = rem.get("strategy", "?")
            rationale = rem.get("rationale", "")
            path = rem.get("path")
            urn = rem.get("urn", "")
            header = f"- **{strategy}**"
            if path:
                header += f" (`{path}`)"
            elif urn:
                header += f" (`{urn}`)"
            lines.append(header)
            if rationale:
                lines.append(f"  - _{rationale}_")

    if ml_impact:
        lines.extend(["", "### ML impact", ""])
        for m in ml_impact:
            lines.append(
                f"- `{m.get('model_urn')}` via `{m.get('via_feature')}`"
                f" → `{m.get('action')}`"
            )

    lines.append("")
    return "\n".join(lines)
