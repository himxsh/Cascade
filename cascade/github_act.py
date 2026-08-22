"""GitHub act helpers — dry-run writes artifacts; live posts when GITHUB_TOKEN is set."""

from __future__ import annotations

import difflib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _enc_ref(branch: str) -> str:
    """URL-encode branch names that contain '/' for Git refs API."""
    return urllib.parse.quote(branch, safe="")


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


def _github_api_list(method: str, path: str, body: dict[str, Any] | None = None) -> list[Any]:
    result = _github_api(method, path, body)
    if isinstance(result, list):
        return result
    return []


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def remediation_branch_name(upstream_pr: int | None) -> str:
    if upstream_pr and upstream_pr > 0:
        return f"cascade/remediation/{upstream_pr}"
    return "cascade/remediation/manual"


COMMENT_MARKER = "## Cascade impact report"


def find_cascade_comment(pr_number: int) -> dict[str, Any] | None:
    """Return the most recent Cascade impact comment on the PR, if any."""
    comments = _github_api_list("GET", f"/issues/{pr_number}/comments?per_page=100")
    found: dict[str, Any] | None = None
    for c in comments:
        body = c.get("body") or ""
        if body.startswith(COMMENT_MARKER):
            found = c
    return found


def write_comment_artifact(out_dir: str | Path, body: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "pr_comment.md"
    path.write_text(body)
    return path


def post_pr_comment(
    body: str,
    *,
    pr_number: int | None = None,
    out_dir: str | Path | None = None,
    force_dry_run: bool = False,
) -> dict[str, Any]:
    """Upsert Cascade comment when GITHUB_TOKEN exists; otherwise write artifact only."""
    if out_dir is not None:
        write_comment_artifact(out_dir, body)

    token = os.environ.get("GITHUB_TOKEN")
    if force_dry_run or not token:
        return {"dry_run": True, "posted": False, "path": str(Path(out_dir or ".") / "pr_comment.md")}

    number = pr_number or int(os.environ.get("CASCADE_PR_NUMBER") or os.environ.get("PR_NUMBER") or "0")
    if number <= 0:
        return {"dry_run": False, "posted": False, "error": "no PR number"}

    existing = find_cascade_comment(number)
    if existing and existing.get("id"):
        result = _github_api("PATCH", f"/issues/comments/{existing['id']}", {"body": body})
        return {
            "dry_run": False,
            "posted": True,
            "updated": True,
            "id": result.get("id") or existing.get("id"),
            "url": result.get("html_url") or existing.get("html_url"),
        }

    result = _github_api("POST", f"/issues/{number}/comments", {"body": body})
    return {
        "dry_run": False,
        "posted": True,
        "updated": False,
        "id": result.get("id"),
        "url": result.get("html_url"),
    }


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


def _repo_owner() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    return repo.split("/", 1)[0]


def commit_files_to_branch(
    files: dict[str, str],
    *,
    branch: str,
    base: str,
    message: str,
    parent_sha: str | None = None,
) -> dict[str, Any]:
    """Create/update branch from base with file contents via Git Data API."""
    if parent_sha:
        base_sha = parent_sha
    else:
        base_ref = _github_api("GET", f"/git/ref/heads/{_enc_ref(base)}")
        base_sha = base_ref["object"]["sha"]
    base_commit = _github_api("GET", f"/git/commits/{base_sha}")
    base_tree = base_commit["tree"]["sha"]

    tree_items: list[dict[str, str]] = []
    for path, content in sorted(files.items()):
        # Normalize to repo-relative path (drop leading ./)
        rel = path.lstrip("./")
        blob = _github_api(
            "POST",
            "/git/blobs",
            {"content": content, "encoding": "utf-8"},
        )
        tree_items.append({
            "path": rel,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })

    tree = _github_api(
        "POST",
        "/git/trees",
        {"base_tree": base_tree, "tree": tree_items},
    )
    commit = _github_api(
        "POST",
        "/git/commits",
        {
            "message": message,
            "tree": tree["sha"],
            "parents": [base_sha],
        },
    )
    commit_sha = commit["sha"]

    try:
        _github_api("GET", f"/git/ref/heads/{_enc_ref(branch)}")
        _github_api(
            "PATCH",
            f"/git/refs/heads/{_enc_ref(branch)}",
            {"sha": commit_sha, "force": True},
        )
        ref_action = "updated"
    except RuntimeError as e:
        if " 404 " not in str(e):
            raise
        _github_api(
            "POST",
            "/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": commit_sha},
        )
        ref_action = "created"

    return {
        "branch": branch,
        "base": base,
        "commit_sha": commit_sha,
        "ref_action": ref_action,
        "files": sorted(files.keys()),
    }


def find_open_pr_for_head(branch: str) -> dict[str, Any] | None:
    owner = _repo_owner()
    head = urllib.parse.quote(f"{owner}:{branch}", safe="")
    pulls = _github_api_list("GET", f"/pulls?state=open&head={head}")
    return pulls[0] if pulls else None


def _stack_refs(upstream: int) -> tuple[str | None, str | None, str | None]:
    """Source PR head ref, base ref, and head SHA."""
    try:
        pull = _github_api("GET", f"/pulls/{upstream}")
    except RuntimeError:
        return None, None, None
    head = pull.get("head") or {}
    base = pull.get("base") or {}
    head_ref = head.get("ref")
    base_ref = base.get("ref")
    head_sha = head.get("sha")
    return (
        str(head_ref) if head_ref else None,
        str(base_ref) if base_ref else None,
        str(head_sha) if head_sha else None,
    )


def request_pr_reviewers(pr_number: int, reviewers: list[str]) -> dict[str, Any]:
    if not reviewers:
        return {"requested": [], "skipped": True}
    try:
        return _github_api(
            "POST",
            f"/pulls/{pr_number}/requested_reviewers",
            {"reviewers": reviewers},
        )
    except RuntimeError as e:
        # ponytail: corpUser→login is best-effort; invalid handles must not fail Act
        return {"requested": [], "error": str(e)}


def open_or_update_downstream_pr(
    files: dict[str, str],
    *,
    title: str = "Cascade: remediate downstream schema break",
    body: str = "",
    out_dir: str | Path | None = None,
    reviewers: list[str] | None = None,
    upstream_pr: int | None = None,
    source_urn: str | None = None,
    force_dry_run: bool = False,
) -> dict[str, Any]:
    """Write rewritten files + unified patch; live open via Git Data API when enabled."""
    patch = build_downstream_patch(files) if files else ""
    reviewers = reviewers or []
    upstream = upstream_pr or int(
        os.environ.get("CASCADE_PR_NUMBER") or os.environ.get("PR_NUMBER") or "0"
    )
    branch = remediation_branch_name(upstream if upstream > 0 else None)
    base = os.environ.get("CASCADE_DOWNSTREAM_BASE", "main").strip() or "main"

    marker = ""
    if source_urn:
        marker = f"\n<!-- cascade:source_urn={source_urn} -->\n"
    pr_md_parts: list[str] = []
    stripped = body.strip()
    if stripped and not stripped.startswith("#"):
        pr_md_parts.extend([f"# {title}", "", stripped])
    elif stripped:
        pr_md_parts.append(stripped)
    else:
        pr_md_parts.extend([f"# {title}", ""])
    pr_md_parts.append(marker)
    if reviewers:
        pr_md_parts.append("## Suggested reviewers")
        pr_md_parts.append("")
        for r in reviewers:
            pr_md_parts.append(f"- @{r}")
        pr_md_parts.append("")
    pr_body = "\n".join(pr_md_parts)

    meta: dict[str, Any] = {
        "title": title,
        "body": body,
        "files": sorted(files.keys()),
        "reviewers": reviewers,
        "branch": branch,
        "base": base,
        "upstream_pr": upstream if upstream > 0 else None,
        "dry_run": True,
        "opened": False,
    }
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta, patch=patch, pr_body=pr_body)

    token = os.environ.get("GITHUB_TOKEN")
    head_override = os.environ.get("CASCADE_DOWNSTREAM_HEAD", "").strip()
    open_via_api = _truthy("CASCADE_OPEN_DOWNSTREAM_PR")

    if force_dry_run or not token or (not open_via_api and not head_override) or not files:
        return {
            "dry_run": True,
            "opened": False,
            "files": sorted(files.keys()),
            "reviewers": reviewers,
            "branch": branch,
            "patch_bytes": len(patch.encode()),
        }

    # Advanced override: open PR from a pre-pushed head (no Git Data commit).
    if head_override and not open_via_api:
        existing = find_open_pr_for_head(head_override)
        if existing:
            pr = _github_api(
                "PATCH",
                f"/pulls/{existing['number']}",
                {"title": title, "body": pr_body},
            )
            action = "updated"
        else:
            pr = _github_api(
                "POST",
                "/pulls",
                {"title": title, "body": pr_body, "head": head_override, "base": base},
            )
            action = "opened"
        request_pr_reviewers(int(pr["number"]), reviewers)
        meta.update({
            "dry_run": False,
            "opened": True,
            "url": pr.get("html_url"),
            "number": pr.get("number"),
            "mode": "head_override",
            "action": action,
            "head": head_override,
        })
        if out_dir is not None:
            write_downstream_artifacts(out_dir, files, meta, patch=patch, pr_body=pr_body)
        return meta

    # Happy path: commit rewrites on top of the source PR head, open/update PR
    # targeting the source PR's base so the stacked PR includes those commits.
    parent = base
    parent_sha = None
    if upstream > 0:
        head_ref, base_ref, head_sha = _stack_refs(upstream)
        if head_sha:
            parent_sha = head_sha
        elif head_ref:
            parent = head_ref
        if base_ref:
            base = base_ref
            meta["base"] = base
    commit_meta = commit_files_to_branch(
        files,
        branch=branch,
        base=parent,
        message=title if upstream <= 0 else f"{title} (from #{upstream})",
        parent_sha=parent_sha,
    )
    existing = find_open_pr_for_head(branch)
    if existing:
        pr = _github_api(
            "PATCH",
            f"/pulls/{existing['number']}",
            {"title": title, "body": pr_body},
        )
        action = "updated"
    else:
        pr = _github_api(
            "POST",
            "/pulls",
            {"title": title, "body": pr_body, "head": branch, "base": base},
        )
        action = "opened"
    review_result = request_pr_reviewers(int(pr["number"]), reviewers)
    meta.update({
        "dry_run": False,
        "opened": True,
        "url": pr.get("html_url"),
        "number": pr.get("number"),
        "mode": "git_data_api",
        "action": action,
        "commit": commit_meta,
        "review_request": review_result,
    })
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta, patch=patch, pr_body=pr_body)
    return meta


_SOURCE_URN_RE = re.compile(
    r"<!--\s*cascade:source_urn=([^>]+?)\s*-->|\*\*Source:\*\*\s*`([^`]+)`",
)


def extract_source_urn_from_pr_body(body: str) -> str | None:
    m = _SOURCE_URN_RE.search(body or "")
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip() or None
