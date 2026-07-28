"""GitHub act helpers — dry-run writes artifacts; live posts when GITHUB_TOKEN is set."""

from __future__ import annotations

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


def write_downstream_artifacts(out_dir: str | Path, files: dict[str, str], meta: dict[str, Any]) -> Path:
    out = Path(out_dir)
    rewritten = out / "rewritten"
    rewritten.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        (rewritten / Path(name).name).write_text(content)
    meta_path = out / "downstream_pr.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")
    return meta_path


def open_or_update_downstream_pr(
    files: dict[str, str],
    *,
    title: str = "Cascade: remediate downstream schema break",
    body: str = "",
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Dry-run writes rewritten files + metadata; live open/update needs GITHUB_TOKEN (Phase 5 depth)."""
    meta: dict[str, Any] = {
        "title": title,
        "body": body,
        "files": sorted(files.keys()),
        "dry_run": True,
    }
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"dry_run": True, "opened": False, "files": sorted(files.keys())}

    # ponytail: live PR create/update is a thin stub — file content is already on disk for Action artifacts.
    # Upgrade: create branch + commit + open/update PR via Contents/Git API (Phase 5 idempotent Action).
    meta["dry_run"] = False
    meta["opened"] = False
    meta["note"] = "GITHUB_TOKEN present; downstream PR live open deferred — artifacts written for Action"
    if out_dir is not None:
        write_downstream_artifacts(out_dir, files, meta)
    return meta
