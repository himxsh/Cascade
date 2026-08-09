"""Minimal .env loader (stdlib). Does not override existing environment variables."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_line(line: str) -> tuple[str, str] | None:
    s = line.strip()
    if not s or s.startswith("#") or "=" not in s:
        return None
    if s.startswith("export "):
        s = s[7:].strip()
    key, _, val = s.partition("=")
    key = key.strip()
    if not key:
        return None
    val = val.strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        val = val[1:-1]
    return key, val


def load_dotenv(path: str | Path | None = None) -> Path | None:
    """Load KEY=VALUE from .env into os.environ (skip keys already set).

    Search order when path is None: cwd/.env, then repo-root/.env (parent of cascade/).
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        candidates.append(Path.cwd() / ".env")
        repo_root = Path(__file__).resolve().parents[1]
        candidates.append(repo_root / ".env")

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        for line in resolved.read_text().splitlines():
            parsed = _parse_line(line)
            if not parsed:
                continue
            key, val = parsed
            if key not in os.environ:
                os.environ[key] = val
        return resolved
    return None
