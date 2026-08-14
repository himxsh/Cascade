"""GitHub markdown: short source-PR comment + human remediation PR body.

Mermaid is filled from ImpactReport (stdlib). The LLM does not write this."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

COMMENT_MARKER = "## Cascade impact report"
_MAX_GRAPH_NODES = 15
_ID_RE = re.compile(r"[^A-Za-z0-9_]")


def _short_name(urn_or_path: str) -> str:
    text = (urn_or_path or "").strip()
    if not text:
        return "unknown"
    if "/" in text or text.endswith(".sql"):
        return Path(text).stem
    parts = text.split(",")
    if len(parts) >= 2:
        return parts[1].rstrip(")").split(".")[-1] or "dataset"
    return text.split(":")[-1] or "node"


def _mid(name: str) -> str:
    s = _ID_RE.sub("_", name).strip("_") or "node"
    if s[0].isdigit():
        s = "n_" + s
    return s


def _renames(changes: list[dict[str, Any]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for c in changes or []:
        if c.get("type") == "FIELD_RENAMED" and c.get("from") and c.get("to"):
            out.append((str(c["from"]), str(c["to"])))
    return out


def _change_phrase(changes: list[dict[str, Any]]) -> str:
    renames = _renames(changes)
    if renames:
        return ", ".join(f"{a} to {b}" for a, b in renames)
    removed = [str(c.get("from")) for c in changes or [] if c.get("type") == "FIELD_REMOVED" and c.get("from")]
    if removed:
        return "removed " + ", ".join(removed)
    return "a schema change"


def _agent_label(remediations: list[dict[str, Any]]) -> str:
    agents = {str(r.get("agent") or "deterministic") for r in remediations or []}
    if agents == {"llm"}:
        return "llm"
    if "llm" in agents:
        return "llm (some nodes fell back to deterministic)"
    return "deterministic"


def blast_mermaid(report: dict[str, Any]) -> str | None:
    source = _short_name(str(report.get("source_urn") or "source"))
    sid = _mid(source)
    phrase = _change_phrase(report.get("changes") or [])
    downstream = report.get("downstream") or []
    if not downstream:
        return None
    shown = downstream[:_MAX_GRAPH_NODES]
    lines = ["flowchart LR", f'  {sid}["{source}: {phrase}"]']
    for node in shown:
        name = _short_name(str(node.get("urn") or "downstream"))
        nid = _mid(name)
        if nid == sid:
            nid = nid + "_d"
        lines.append(f'  {nid}["{name}"]')
        lines.append(f"  {sid} --> {nid}")
    extra = len(downstream) - len(shown)
    if extra > 0:
        lines.append(f'  more["{extra} more downstream"]')
        lines.append(f"  {sid} --> more")
    return "\n".join(lines)


def fix_mermaid(report: dict[str, Any]) -> str | None:
    remediations = report.get("remediations") or []
    if not remediations:
        return None
    phrase = _change_phrase(report.get("changes") or [])
    n = len(report.get("downstream") or remediations)
    lines = [
        "flowchart TD",
        f'  change["{phrase}"]',
        f'  blast["{n} downstream models"]',
        "  change --> blast",
    ]
    for i, rem in enumerate(remediations[:_MAX_GRAPH_NODES]):
        label = _short_name(str(rem.get("path") or rem.get("urn") or f"node{i}"))
        strategy = rem.get("strategy") or "fix"
        agent = rem.get("agent") or "deterministic"
        rid = f"r{i}"
        lines.append(f'  {rid}["{label}: {strategy} ({agent})"]')
        lines.append(f"  blast --> {rid}")
    extra = len(remediations) - min(len(remediations), _MAX_GRAPH_NODES)
    if extra > 0:
        lines.append(f'  rmore["{extra} more fixes"]')
        lines.append("  blast --> rmore")
    return "\n".join(lines)


def build_remediation_title(report: dict[str, Any]) -> str:
    n = len(report.get("downstream") or [])
    renames = _renames(report.get("changes") or [])
    if renames:
        a, b = renames[0]
        return f"Fix {n} downstream models after {a} → {b}"
    return f"Fix {n} downstream models after schema change"


def build_pr_comment(
    report: dict[str, Any],
    *,
    remediation_pr_url: str | None = None,
) -> str:
    """Short comment on the source (breaking) PR."""
    source = _short_name(str(report.get("source_urn") or "unknown"))
    severity = report.get("severity", "unknown")
    n = len(report.get("downstream") or [])
    phrase = _change_phrase(report.get("changes") or [])
    remediations = report.get("remediations") or []
    agent = _agent_label(remediations)
    lines = [
        COMMENT_MARKER,
        "",
        f"**What changed:** {phrase} on `{source}`",
        f"**Downstream:** {n} models ({severity})",
        f"**Agent:** {agent}",
        "",
    ]
    graph = blast_mermaid(report)
    if graph:
        lines.extend(["```mermaid", graph, "```", ""])
    if remediation_pr_url:
        lines.append(f"**Remediation PR:** {remediation_pr_url}")
        lines.append("")
    elif remediations:
        lines.append("Cascade opened (or will open) a remediation PR with the SQL fix.")
        lines.append("")
    ml_impact = report.get("ml_impact") or []
    if ml_impact:
        lines.append("**ML:** retrain suggested for " + ", ".join(
            f"`{_short_name(str(m.get('model_urn')))}`" for m in ml_impact
        ))
        lines.append("")
    lines.append(f"**Source:** `{report.get('source_urn', '(unknown)')}`")
    lines.append("")
    return "\n".join(lines)


def build_remediation_pr_body(report: dict[str, Any]) -> str:
    """Human-readable remediation PR. No unified diff — files are the diff."""
    source = _short_name(str(report.get("source_urn") or "unknown"))
    severity = report.get("severity", "unknown")
    n = len(report.get("downstream") or [])
    phrase = _change_phrase(report.get("changes") or [])
    remediations = report.get("remediations") or []
    agent = _agent_label(remediations)
    title = build_remediation_title(report)
    lines = [
        f"# {title}",
        "",
        f"A breaking schema change on **{source}** ({phrase}) would break **{n}** downstream models.",
        "This PR applies Cascade's rewrite so those models keep working.",
        "",
        f"- **Severity:** {severity}",
        f"- **Agent:** {agent}",
        "",
        "## What could break",
        "",
    ]
    graph = blast_mermaid(report)
    if graph:
        lines.extend(["```mermaid", graph, "```", ""])
    else:
        lines.append("_No downstream models in the impact report._")
        lines.append("")
    lines.extend(["## How Cascade fixed it", ""])
    flow = fix_mermaid(report)
    if flow:
        lines.extend(["```mermaid", flow, "```", ""])
    else:
        lines.append("_No remediations generated._")
        lines.append("")
    lines.extend(["## Files in this PR", ""])
    files = [r for r in remediations if r.get("path") and r.get("rewritten_sql")]
    if not files:
        lines.append("_No SQL files rewritten (adapter/deprecate only)._")
        lines.append("")
    else:
        for rem in files:
            rationale = (rem.get("rationale") or "").strip()
            extra = f" — {rationale}" if rationale else ""
            lines.append(
                f"- `{rem['path']}` — {rem.get('strategy', 'rewrite')} "
                f"({rem.get('agent') or 'deterministic'}){extra}"
            )
        lines.append("")
    others = [r for r in remediations if not (r.get("path") and r.get("rewritten_sql"))]
    if others:
        lines.extend(["## Other actions", ""])
        for rem in others:
            name = _short_name(str(rem.get("urn") or rem.get("path") or "node"))
            lines.append(
                f"- **{rem.get('strategy')}** `{name}` — {rem.get('rationale') or ''}"
            )
        lines.append("")
    lines.extend([
        "<details>",
        "<summary>Details (URNs, owners, ML)</summary>",
        "",
        f"**Source:** `{report.get('source_urn', '(unknown)')}`",
        "",
    ])
    for node in report.get("downstream") or []:
        owners = ", ".join(node.get("owners") or []) or "(none)"
        lines.append(f"- `{node.get('urn')}` — owners: {owners}")
    for m in report.get("ml_impact") or []:
        lines.append(
            f"- ML `{m.get('model_urn')}` via `{m.get('via_feature')}` → `{m.get('action')}`"
        )
    lines.extend(["", "</details>", ""])
    return "\n".join(lines)
