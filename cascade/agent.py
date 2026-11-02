"""LLM remediation for downstream models, with disabled mode as report only."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from cascade.config import (
    CascadeConfig,
    load_config,
    resolve_model_path,
    resolve_rewrite_mode,
)
from cascade.datahub_fixture import fields_from_changes, get_downstream_lineage

_PROVIDER_BASE = {
    "openai": "https://api.openai.com/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}
_BASE_URL_REQUIRED = frozenset({"azure-openai", "bedrock", "anthropic", "custom"})
_DEFAULT_TIMEOUT_SEC = 180
_DEFAULT_MAX_LATENCY_MS = 180_000
_MAX_CONTEXT_CHARS = 400_000
_REWRITE_SKILL_PATH = Path(__file__).resolve().parent / "prompts" / "rewrite_skill.md"
_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["path", "content", "reason"],
                "additionalProperties": False,
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["files", "notes"],
    "additionalProperties": False,
}


def _rewrite_skill_text() -> str:
    return _REWRITE_SKILL_PATH.read_text()


def _llm_timeout_sec() -> float:
    try:
        return max(1.0, float(os.environ.get("LLM_TIMEOUT_SEC", "180")))
    except ValueError:
        return 180.0


def _rewrite_provider(cfg: CascadeConfig) -> str:
    return (os.environ.get("CASCADE_LLM_PROVIDER") or cfg.rewrite_provider or "openai").strip().lower()


def _llm_model(cfg: CascadeConfig) -> str:
    return (os.environ.get("LLM_MODEL") or cfg.rewrite_model or "").strip()


def _llm_base_url(cfg: CascadeConfig) -> str | None:
    explicit = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    provider = _rewrite_provider(cfg)
    return _PROVIDER_BASE.get(provider) or (
        None if provider in _BASE_URL_REQUIRED else _PROVIDER_BASE["openai"]
    )


def _llm_max_latency_ms() -> int:
    try:
        return max(1000, int(os.environ.get("LLM_MAX_LATENCY_MS", "180000")))
    except ValueError:
        return 180_000


def _model_path_for_urn(
    urn: str,
    models_dir: str | Path | None,
    urn_files: dict[str, str] | None = None,
) -> Path | None:
    return resolve_model_path(urn, models_dir, urn_files)


def _all_downstream_urns(
    catalog: dict[str, Any],
    source_urn: str | None,
    changes: list[dict[str, Any]] | None = None,
) -> list[str]:
    return get_downstream_lineage(
        source_urn or "", catalog, fields=fields_from_changes(changes or []) or None
    )


def _log_agent(msg: str) -> None:
    print(f"cascade: {msg}", file=sys.stderr)


def _valid_reply(parsed: Any) -> bool:
    return (
        isinstance(parsed, dict)
        and isinstance(parsed.get("files"), list)
        and isinstance(parsed.get("notes"), str)
        and all(
            isinstance(item, dict)
            and all(isinstance(item.get(key), str) for key in ("path", "content", "reason"))
            for item in parsed["files"]
        )
    )


def _call_llm(prompt: str, cfg: CascadeConfig) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base, model = _llm_base_url(cfg), _llm_model(cfg)
    if not key:
        raise RuntimeError("cascade: CASCADE_MODE=llm requires LLM_API_KEY or OPENAI_API_KEY")
    if not model:
        raise RuntimeError("cascade: CASCADE_MODE=llm requires LLM_MODEL")
    if not base:
        raise RuntimeError(f"cascade: provider {_rewrite_provider(cfg)!r} requires LLM_BASE_URL")
    schema = _REPLY_SCHEMA
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "cascade_remediation",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    ).encode()
    meta = {"model": model, "latency_ms": 0}
    for attempt in range(2):
        started = time.monotonic()
        try:
            req = Request(
                f"{base}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
                method="POST",
            )
            with urlopen(req, timeout=_llm_timeout_sec()) as resp:
                data = json.loads(resp.read().decode())
            meta["latency_ms"] = int((time.monotonic() - started) * 1000)
            if meta["latency_ms"] > _llm_max_latency_ms():
                raise TimeoutError("latency_budget")
            value = data["choices"][0]["message"]["content"].strip()
            if value.startswith("```"):
                value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(value)
            if not _valid_reply(parsed):
                raise ValueError("invalid_shape")
            return parsed, meta
        except Exception as e:
            meta["latency_ms"] = int((time.monotonic() - started) * 1000)
            meta["error"] = type(e).__name__
    return None, meta


def choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None = None,
    source_urn: str | None = None,
    urn_files: dict[str, str] | None = None,
    rewrite_mode: str | None = None,
    config: CascadeConfig | None = None,
    *,
    diff_text: str | None = None,
    source_urns: list[str] | None = None,
) -> list[dict[str, Any]]:
    cfg = config if config is not None else load_config()
    files = urn_files if urn_files is not None else cfg.urn_files
    mode = resolve_rewrite_mode(rewrite_mode, config=cfg)
    if mode != "llm":
        _log_agent("agent=none reason=mode")
        return []
    source_urns = source_urns or ([source_urn] if source_urn else [])
    downstream = []
    for source in source_urns:
        for urn in _all_downstream_urns(catalog, source, changes):
            if urn not in downstream:
                downstream.append(urn)
    by_path = {}
    lineage = []
    for urn in downstream:
        p = _model_path_for_urn(urn, models_dir, files)
        lineage.append({"urn": urn, "path": str(p) if p else None})
        if p and p.is_file():
            by_path[str(p)] = p
    if not by_path:
        _log_agent("agent=none reason=no_files")
        return []
    root = Path.cwd()
    paths = list(by_path.values())
    for p in list(paths):
        try:
            content = p.read_text()
        except OSError:
            continue
        for name in re.findall(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)", content):
            found = next(iter(Path(models_dir).rglob(name + ".sql")), None) if models_dir else None
            if found:
                by_path[str(found)] = found
    for source in source_urns:
        source_path = _model_path_for_urn(source, models_dir, files)
        if source_path and source_path.is_file():
            by_path[str(source_path)] = source_path
    macros = root / "macros"
    if macros.exists():
        for p in macros.rglob("*.sql"):
            by_path[str(p)] = p
    if models_dir:
        for pat in ("*.yml", "*.yaml"):
            for p in Path(models_dir).rglob(pat):
                by_path[str(p)] = p
    contents = {}
    for key, path in by_path.items():
        try:
            contents[key] = path.read_text()
        except OSError:
            continue
    if sum(map(len, contents.values())) > _MAX_CONTEXT_CHARS:
        _log_agent("agent=none reason=context_too_large")
        return []
    prompt = _rewrite_skill_text().strip() + "\n\n"
    if diff_text is not None:
        prompt += "PR diff:\n" + diff_text + "\n\n"
    prompt += "Changes: " + json.dumps(changes) + "\nLineage: " + json.dumps(lineage) + "\n"
    for path, content in contents.items():
        prompt += f'<file path="{path}">\n{content}\n</file>\n'
    parsed, meta = _call_llm(prompt, cfg)
    if parsed is None:
        _log_agent(f"agent=none reason={meta.get('error', 'llm_failed')}")
        return []
    if any(f["path"] not in contents for f in parsed["files"]):
        _log_agent("agent=none reason=bad_path")
        return []
    out = []
    urn_for = {
        str(_model_path_for_urn(u, models_dir, files)): u
        for u in downstream
        if _model_path_for_urn(u, models_dir, files)
    }
    for f in parsed["files"]:
        if f["content"] == contents[f["path"]]:
            continue
        out.append(
            {
                "urn": urn_for.get(f["path"]),
                "path": f["path"],
                "strategy": "rewrite",
                "rationale": f["reason"],
                "rewritten_sql": f["content"],
                "agent": "llm",
            }
        )
    _log_agent(f"agent=llm files={len(out)} model={meta['model']} latency_ms={meta['latency_ms']}")
    return out
