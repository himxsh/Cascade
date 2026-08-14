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
    urn_files: dict[str, str] = field(default_factory=dict)  # urn → SQL path
    rewrite_mode: str | None = None  # deterministic | llm
    rewrite_provider: str | None = None
    rewrite_model: str | None = None


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
    urn_files: dict[str, str] = {}
    raw_files = data.get("urn_files") or {}
    if isinstance(raw_files, dict):
        for urn, fpath in raw_files.items():
            urn_files[str(urn)] = _normalize_prefix(str(fpath))
    rewrite = data.get("rewrite") if isinstance(data.get("rewrite"), dict) else {}
    mode = str(rewrite.get("mode") or "").strip().lower() or None
    provider = str(rewrite.get("provider") or "").strip().lower() or None
    model = str(rewrite.get("model") or "").strip() or None
    return CascadeConfig(
        mappings=mappings,
        default_urn=str(default_urn) if default_urn else None,
        models_dir=str(models_dir) if models_dir else None,
        urn_files=urn_files,
        rewrite_mode=mode if mode in ("deterministic", "llm") else None,
        rewrite_provider=provider,
        rewrite_model=model,
    )


def _urn_stem(urn: str) -> str | None:
    """Last segment of the dataset name inside a dataset URN."""
    parts = urn.split(",")
    if len(parts) < 2:
        return None
    name = parts[1].rstrip(")")
    return name.split(".")[-1] or None


def resolve_model_path(
    urn: str,
    models_dir: str | Path | None,
    urn_files: dict[str, str] | None = None,
) -> Path | None:
    """Map dataset URN → SQL file: explicit urn_files → recursive search → flat path."""
    if urn_files and urn in urn_files:
        p = Path(urn_files[urn])
        return p if p.is_file() else None
    if not models_dir:
        return None
    stem = _urn_stem(urn)
    if not stem:
        return None
    root = Path(models_dir)
    if not root.is_dir():
        flat = root / f"{stem}.sql"
        return flat if flat.is_file() else None
    matches = sorted(
        (p for p in root.rglob(f"{stem}.sql") if p.is_file()),
        key=lambda p: (len(p.parts), str(p)),
    )
    if matches:
        return matches[0]
    return None


def resolve_urn(
    paths: list[str],
    config: CascadeConfig,
    *,
    explicit: str | None = None,
    env: str | None = None,
) -> str:
    """Resolve source dataset URN: explicit → path mapping → env → default_urn."""
    urns = resolve_urns(paths, config, explicit=explicit, env=env)
    return urns[0]


def resolve_urns(
    paths: list[str],
    config: CascadeConfig,
    *,
    explicit: str | None = None,
    env: str | None = None,
) -> list[str]:
    """Resolve one or more source URNs for a multi-file change set (stable order)."""
    if explicit:
        return [explicit]
    found: list[str] = []
    seen: set[str] = set()
    for path in paths:
        norm = _normalize_prefix(path)
        matched: str | None = None
        for prefix, urn in config.mappings:
            p = prefix.rstrip("/")
            if not p:
                continue
            if norm == p or norm.startswith(p + "/"):
                matched = urn
                break
        if matched and matched not in seen:
            seen.add(matched)
            found.append(matched)
    env_urn = env if env is not None else os.environ.get("CASCADE_SOURCE_URN")
    if not found and env_urn:
        return [env_urn]
    if not found and config.default_urn:
        return [config.default_urn]
    if not found:
        raise SystemExit(
            "cascade: cannot resolve source URN — pass --urn, set CASCADE_SOURCE_URN, "
            "or add a path mapping / default_urn in .cascade/config.json"
        )
    return found


def changes_for_urn(
    changes: list[dict[str, Any]],
    urn: str,
    config: CascadeConfig,
) -> list[dict[str, Any]]:
    """Filter diff changes that belong to files mapped to this source URN."""
    out: list[dict[str, Any]] = []
    for change in changes:
        path = change.get("path")
        if not path:
            # JSON / pathless changes apply to every resolved source
            out.append({k: v for k, v in change.items() if k != "path"})
            continue
        try:
            mapped = resolve_urn([str(path)], config)
        except SystemExit:
            continue
        if mapped == urn:
            out.append({k: v for k, v in change.items() if k != "path"})
    return out


def resolve_rewrite_mode(
    cli: str | None = None,
    config: CascadeConfig | None = None,
) -> str:
    """CLI flag → CASCADE_MODE → config rewrite.mode → deterministic."""
    if cli in ("deterministic", "llm"):
        return cli
    env = os.environ.get("CASCADE_MODE", "").strip().lower()
    if env in ("deterministic", "llm"):
        return env
    cfg = config if config is not None else load_config()
    if cfg.rewrite_mode in ("deterministic", "llm"):
        return cfg.rewrite_mode
    return "deterministic"
