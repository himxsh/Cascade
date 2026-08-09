"""Thin repo config: path prefix → dataset URN (stdlib JSON only)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CascadeConfig:
    mappings: list[tuple[str, str]] = field(default_factory=list)  # (path_prefix, urn)
    default_urn: str | None = None
    models_dir: str | None = None


def _normalize_prefix(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def load_config(path: str | Path | None = None) -> CascadeConfig:
    """Load `.cascade/config.json` (or explicit path). Missing file → empty config."""
    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        root = Path.cwd()
        candidates.append(root / ".cascade" / "config.json")
        candidates.append(root / "cascade.json")

    for candidate in candidates:
        if not candidate.is_file():
            continue
        data = json.loads(candidate.read_text())
        return _parse(data)
    return CascadeConfig()


def _parse(data: dict[str, Any]) -> CascadeConfig:
    mappings: list[tuple[str, str]] = []
    raw = data.get("mappings") or []
    if isinstance(raw, dict):
        # {"path/prefix": "urn:..."} shorthand
        for prefix, urn in raw.items():
            mappings.append((_normalize_prefix(str(prefix)), str(urn)))
    else:
        for item in raw:
            if isinstance(item, dict) and item.get("path") and item.get("urn"):
                mappings.append((_normalize_prefix(str(item["path"])), str(item["urn"])))
    # Longest prefix first for resolve
    mappings.sort(key=lambda p: len(p[0]), reverse=True)
    default_urn = data.get("default_urn") or data.get("urn")
    models_dir = data.get("models_dir")
    return CascadeConfig(
        mappings=mappings,
        default_urn=str(default_urn) if default_urn else None,
        models_dir=str(models_dir) if models_dir else None,
    )


def resolve_urn(
    paths: list[str],
    config: CascadeConfig,
    *,
    explicit: str | None = None,
    env: str | None = None,
) -> str:
    """Resolve source dataset URN: explicit → path mapping → env → default_urn."""
    if explicit:
        return explicit
    for path in paths:
        norm = _normalize_prefix(path)
        for prefix, urn in config.mappings:
            p = prefix.rstrip("/")
            if not p:
                continue
            if norm == p or norm.startswith(p + "/"):
                return urn
    env_urn = env if env is not None else os.environ.get("CASCADE_SOURCE_URN")
    if env_urn:
        return env_urn
    if config.default_urn:
        return config.default_urn
    raise SystemExit(
        "cascade: cannot resolve source URN — pass --urn, set CASCADE_SOURCE_URN, "
        "or add a path mapping / default_urn in .cascade/config.json"
    )
