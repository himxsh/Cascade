"""GitHub act helpers — dry-run writes artifacts; live posts when GITHUB_TOKEN is set."""

from __future__ import annotations

import difflib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _github_api(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN not set")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY not set")
    url = f"https://api.github.com/repos/{repo}{path}"
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"GitHub API {method} {path} failed: {e.code} {detail}") from e


def write_comment_artifact(out_dir: str | Path, body: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "pr_comment.md"
    path.write_text(body)
    return path


def post_pr_comment(body: str, *, pr_number: int | None = None, out_dir: str | Path | None = None) -> dict[str, Any]:
    """Post comment when GITHUB_TOKEN exists; otherwise write pr_comment.md under out_dir."""
    if out_dir is not None:
        write_comment_artifact(out_dir, body)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"dry_run": True, "posted": False, "path": str(Path(out_dir or ".") / "pr_comment.md")}

    number = pr_number or int(os.environ.get("CASCADE_PR_NUMBER") or os.environ.get("PR_NUMBER") or "0")
    if number <= 0:
        return {"dry_run": False, "posted": False, "error": "no PR number"}

    result = _github_api("POST", f"/issues/{number}/comments", {"body": body})
    return {"dry_run": False, "posted": True, "id": result.get("id"), "url": result.get("html_url")}


def build_unified_diff(path: str, old: str, new: str) -> str:
    """Minimal unified diff (stdlib difflib) for one file."""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    if old_lines and not old_lines[-1].endswith("\n"):
        old_lines[-1] += "\n"
    if new_lines and not new_lines[-1].endswith("\n"):
        new_lines[-1] += "\n"
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="\n",
        )
    )


def build_downstream_patch(files: dict[str, str]) -> str:
    """Build a multi-file unified diff from rewritten SQL paths (read originals when present)."""
    chunks: list[str] = []
    for path, new_content in sorted(files.items()):
        src = Path(path)
        old = src.read_text() if src.exists() else ""
        rel = path if not path.startswith("/") else src.name
        diff = build_unified_diff(rel, old, new_content)
        if diff:
            chunks.append(diff)
    return "".join(chunks)


def owner_urns_to_reviewers(owner_urns: list[str]) -> list[str]:
    """Map DataHub corpUser URNs to GitHub-ish handles (local part after corpuser:)."""
    out: list[str] = []
    for urn in owner_urns:
        if "corpuser:" in urn:
            handle = urn.rsplit("corpuser:", 1)[-1].rstrip(")")
            if handle and handle not in out:
                out.append(handle)
    return out


def write_downstream_artifacts(
    out_dir: str | Path,
    files: dict[str, str],
    meta: dict[str, Any],
    *,
    patch: str | None = None,
    pr_body: str | None = None,
) -> Path:
    out = Path(out_dir)
    rewritten = out / "rewritten"
    rewritten.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (rewritten / Path(name).name).write_text(content)
    if patch is not None:
        (out / "downstream_pr.diff").write_text(patch)
    if pr_body is not None:
        (out / "downstream_pr.md").write_text(pr_body)
    meta_path = out / "downstream_pr.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta_path


def open_or_update_downstream_pr(
    files: dict[str, str],
    *,
    title: str = "Cascade: remediate downstream schema break",
    body: str = "",
    out_dir: str | Path | None = None,
    reviewers: list[str] | None = None,
) -> dict[str, Any]:
    """Write rewritten files + unified patch; live open when CASCADE_OPEN_DOWNSTREAM_PR=1 + token."""
    patch = build_downstream_patch(files) if files else ""
    reviewers = reviewers or []
    pr_md_parts = [f"# {title}", "", body.strip(), ""]
    if reviewers:
        pr_md_parts.append("## Suggested reviewers")
        pr_md_parts.append("")
        for r in reviewers:
            pr_md_parts.append(f"- @{r}")
        pr_md_parts.append("")
    if patch:
        pr_md_parts.append("## Patch")
        pr_md_parts.append("")
        pr_md_parts.append("```diff")
        pr_md_parts.append(patch.rstrip())
        pr_md_parts.append("```")
        pr_md_parts.append("")
    pr_body = "\n".join(pr_md_parts)

    meta: dict[str, Any] = {
        "title": title,
        "body": body,
        "files": sorted(files.keys()),
        "reviewers": reviewers,
        "dry_run": True,
        "opened": False,
    }
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta, patch=patch, pr_body=pr_body)

    token = os.environ.get("GITHUB_TOKEN")
    head = os.environ.get("CASCADE_DOWNSTREAM_HEAD", "").strip()
    # ponytail: live PR only when a pushed head branch already has the rewrite.
    # Default path writes patch artifacts. Upgrade (Phase 5): Git Data API branch+commit.
    if not token or not head:
        return {
            "dry_run": True,
            "opened": False,
            "files": sorted(files.keys()),
            "reviewers": reviewers,
            "patch_bytes": len(patch.encode()),
        }

    head_base = os.environ.get("CASCADE_DOWNSTREAM_BASE", "main")
    pr = _github_api(
        "POST",
        "/pulls",
        {
            "title": title,
            "body": pr_body,
            "head": head,
            "base": head_base,
        },
    )
    meta.update({
        "dry_run": False,
        "opened": True,
        "url": pr.get("html_url"),
        "number": pr.get("number"),
        "mode": "pull_request",
        "reviewers": reviewers,
    })
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta, patch=patch, pr_body=pr_body)
    return meta