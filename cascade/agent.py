"""Agent: choose remediation strategy + rewrite downstream SQL.

LLM is used only when CASCADE_MODE=llm (or --rewrite llm) and a key is set.
Deterministic rewrite is the default. LLM also falls back when:
  - transport/parse failure
  - schema-gate rejects LLM SQL
  - latency exceeds LLM_MAX_LATENCY_MS (or request hits LLM_TIMEOUT_SEC)
"""

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

from cascade.config import CascadeConfig, load_config, resolve_model_path, resolve_rewrite_mode
from cascade.datahub_fixture import fields_from_changes, get_downstream_lineage
from cascade.schema_gate import validate_rename_semantics, validate_sql
from cascade.rewrite import rename_column

_LLM_CHAT_URL_RE = re.compile(r"^(https?://.+)/chat/completions$")
_PROVIDER_BASE = {
    "openai": "https://api.openai.com/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}
_BASE_URL_REQUIRED = frozenset({"azure-openai", "bedrock", "anthropic", "custom"})
_DEFAULT_TIMEOUT_SEC = 15
_DEFAULT_MAX_LATENCY_MS = 15_000
_REWRITE_SKILL_PATH = Path(__file__).resolve().parent / "prompts" / "rewrite_skill.md"


def _rewrite_skill_text() -> str:
    try:
        return _REWRITE_SKILL_PATH.read_text()
    except OSError:
        return (
            "Closed world: edit only what Changes lists. Read new upstream "
            "names; never from AS to; never invent lookalike renames; "
            "prefer adapter_view/deprecate over guessing."
        )


def _llm_timeout_sec() -> float:
    raw = os.environ.get("LLM_TIMEOUT_SEC", "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return float(_DEFAULT_TIMEOUT_SEC)


def _rewrite_provider(cfg: CascadeConfig) -> str:
    env = os.environ.get("CASCADE_LLM_PROVIDER", "").strip().lower()
    if env:
        return env
    return (cfg.rewrite_provider or "openai").strip().lower() or "openai"


def _llm_model(cfg: CascadeConfig) -> str:
    env = os.environ.get("LLM_MODEL", "").strip()
    if env:
        return env
    return (cfg.rewrite_model or "").strip()


def _llm_base_url(cfg: CascadeConfig) -> str | None:
    explicit = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    provider = _rewrite_provider(cfg)
    if provider in _PROVIDER_BASE:
        return _PROVIDER_BASE[provider]
    if provider in _BASE_URL_REQUIRED:
        return None
    return _PROVIDER_BASE["openai"]


def _llm_max_latency_ms() -> int:
    raw = os.environ.get("LLM_MAX_LATENCY_MS", "").strip()
    if raw:
        try:
            return max(1000, int(raw))
        except ValueError:
            pass
    return int(_DEFAULT_MAX_LATENCY_MS)


def _model_path_for_urn(
    urn: str,
    models_dir: str | Path | None,
    urn_files: dict[str, str] | None = None,
) -> Path | None:
    return resolve_model_path(urn, models_dir, urn_files)


def _change_column_names(changes: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for c in changes:
        for key in ("from", "to"):
            val = c.get(key)
            if val:
                names.add(str(val))
    return names


def _all_downstream_urns(
    catalog: dict[str, Any],
    source_urn: str | None,
    changes: list[dict[str, Any]] | None = None,
) -> list[str]:
    fields = fields_from_changes(changes or [])
    return get_downstream_lineage(
        source_urn or "", catalog, fields=fields or None
    )


def _upstream_urns(catalog: dict[str, Any], urn: str) -> list[str]:
    """Transitive upstreams via inverted downstream_map."""
    downstream_map = catalog.get("downstream_map", {})
    parents: dict[str, list[str]] = {}
    for src, children in downstream_map.items():
        for child in children:
            parents.setdefault(child, []).append(src)
    out: list[str] = []
    seen: set[str] = set()
    queue = list(parents.get(urn, []))
    while queue:
        cur = queue.pop(0)
        if cur in seen:
            continue
        seen.add(cur)
        out.append(cur)
        queue.extend(parents.get(cur, []))
    return out


def _allowed_columns(
    catalog: dict[str, Any], urn: str, changes: list[dict[str, Any]]
) -> set[str]:
    # Own fields + transitive upstream fields + explicit rename endpoints.
    # ponytail: not whole-catalog — that let unrelated rename targets pass.
    datasets_by_urn = catalog.get("datasets_by_urn", {})
    names: set[str] = set()
    for u in [urn, *_upstream_urns(catalog, urn)]:
        ds = datasets_by_urn.get(u, {})
        for f in ds.get("schema_fields", []):
            names.add(f["name"])
    return names | _change_column_names(changes)


def _log_agent(msg: str) -> None:
    print(f"cascade: {msg}", file=sys.stderr)


def _demo_choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None,
    source_urn: str | None,
    urn_files: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    remediations: list[dict[str, Any]] = []
    datasets_by_urn = catalog.get("datasets_by_urn", {})

    renames: dict[str, str] = {}
    has_field_removed = any(c["type"] == "FIELD_REMOVED" and not c.get("to") for c in changes)
    for c in changes:
        if c["type"] == "FIELD_RENAMED" and c.get("from") and c.get("to"):
            renames[c["from"]] = c["to"]

    all_downstream = _all_downstream_urns(catalog, source_urn, changes)
    handled_urns: set[str] = set()

    for urn in all_downstream:
        allowed_base = _allowed_columns(catalog, urn, changes)

        for old_name, new_name in renames.items():
            model_path = _model_path_for_urn(urn, models_dir, urn_files)
            if model_path:
                sql = model_path.read_text()
                if old_name in sql:
                    rewritten = rename_column(sql, old_name, new_name)
                    try:
                        validate_sql(rewritten, allowed_base)
                    except ValueError:
                        remediations.append({
                            "urn": urn,
                            "strategy": "adapter_view",
                            "rationale": (
                                f"rewrite of {old_name}->{new_name} in "
                                f"{model_path.name} failed schema gate; "
                                f"falling back to adapter view"
                            ),
                            "agent": "deterministic",
                        })
                        handled_urns.add(urn)
                        continue

                    remediations.append({
                        "urn": urn,
                        "path": str(model_path),
                        "strategy": "rewrite",
                        "rationale": (
                            f"downstream SQL {model_path.name} references "
                            f"{old_name} in SELECT/JOIN; rewriting to "
                            f"{new_name} to match upstream schema change"
                        ),
                        "rewritten_sql": rewritten,
                        "agent": "deterministic",
                    })
                    handled_urns.add(urn)
            else:
                remediations.append({
                    "urn": urn,
                    "strategy": "adapter_view",
                    "rationale": (
                        f"no SQL model found for downstream node; "
                        f"recommend adapter view to alias {old_name}->{new_name} "
                        f"while downstream migrates"
                    ),
                    "agent": "deterministic",
                })
                handled_urns.add(urn)

    if has_field_removed:
        for urn in all_downstream:
            if urn not in handled_urns:
                remediations.append({
                    "urn": urn,
                    "strategy": "deprecate",
                    "rationale": (
                        f"FIELD_REMOVED with no replacement column; "
                        f"mark downstream node {urn} as deprecated"
                    ),
                    "agent": "deterministic",
                })
                handled_urns.add(urn)

    return remediations


def _call_llm(
    changes: list[dict[str, Any]],
    downstream_info: list[dict[str, Any]],
    model_sql: str | None,
    cfg: CascadeConfig | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Returns (parsed_json_or_None, meta). Meta never includes secrets."""
    cfg = cfg if cfg is not None else load_config()
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = _llm_base_url(cfg)
    model = _llm_model(cfg)
    meta: dict[str, Any] = {"model": model, "latency_ms": None, "ok": False, "error": None}
    if not api_key:
        meta["error"] = "no_api_key"
        return None, meta
    if not model:
        meta["error"] = "no_model"
        return None, meta
    if not base_url:
        meta["error"] = "no_base_url"
        return None, meta

    prompt = (
        f"{_rewrite_skill_text().strip()}\n\n"
        f"Changes: {json.dumps(changes)}\n"
        f"Downstream info: {json.dumps(downstream_info)}\n"
    )
    if model_sql is not None:
        prompt += f"Model SQL:\n{model_sql}\n"

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "cascade_remediation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "strategy": {
                            "type": "string",
                            "enum": ["rewrite", "adapter_view", "deprecate"],
                        },
                        "rationale": {"type": "string"},
                        "sql": {"type": ["string", "null"]},
                    },
                    "required": ["strategy", "rationale", "sql"],
                    "additionalProperties": False,
                },
            },
        },
    }).encode()

    req = Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urlopen(req, timeout=_llm_timeout_sec()) as resp:
            data = json.loads(resp.read().decode())
        meta["latency_ms"] = int((time.monotonic() - t0) * 1000)
        text = data["choices"][0]["message"]["content"]
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        parsed = json.loads(cleaned.strip())
        if meta["latency_ms"] > _llm_max_latency_ms():
            meta["error"] = "latency_budget"
            return None, meta
        meta["ok"] = True
        return parsed, meta
    except (TimeoutError, URLError, HTTPError, json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        meta["latency_ms"] = int((time.monotonic() - t0) * 1000)
        meta["error"] = type(e).__name__
        return None, meta
    except Exception as e:
        meta["latency_ms"] = int((time.monotonic() - t0) * 1000)
        meta["error"] = type(e).__name__
        return None, meta


def _rem_from_llm(
    urn: str,
    llm: dict[str, Any],
    *,
    model_path: Path | None,
    allowed: set[str],
    changes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    strategy = llm.get("strategy")
    if strategy not in ("rewrite", "adapter_view", "deprecate"):
        return None
    rationale = (llm.get("rationale") or "").strip() or "LLM remediation"
    if strategy == "rewrite":
        rewritten = llm.get("sql")
        if not rewritten or not model_path:
            return None
        # raises ValueError → caller falls back to deterministic
        validate_sql(rewritten, allowed)
        validate_rename_semantics(rewritten, changes)
        return {
            "urn": urn,
            "path": str(model_path),
            "strategy": "rewrite",
            "rationale": rationale,
            "rewritten_sql": rewritten,
            "agent": "llm",
        }
    return {
        "urn": urn,
        "strategy": strategy,
        "rationale": rationale,
        "agent": "llm",
    }


# ponytail: OpenAI-compatible HTTP; named providers set LLM_BASE_URL, no Mantle default
def choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None = None,
    source_urn: str | None = None,
    urn_files: dict[str, str] | None = None,
    rewrite_mode: str | None = None,
    config: CascadeConfig | None = None,
) -> list[dict[str, Any]]:
    """Deterministic by default; LLM only when mode=llm and keyed."""
    cfg = config if config is not None else load_config()
    files = urn_files if urn_files is not None else cfg.urn_files
    demo = _demo_choose_and_rewrite(changes, catalog, models_dir, source_urn, files)
    mode = resolve_rewrite_mode(rewrite_mode, config=cfg)
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if mode != "llm":
        _log_agent("agent=deterministic reason=mode")
        return demo
    if not api_key:
        raise RuntimeError(
            "cascade: CASCADE_MODE=llm requires LLM_API_KEY or OPENAI_API_KEY"
        )
    if not _llm_model(cfg):
        raise RuntimeError("cascade: CASCADE_MODE=llm requires LLM_MODEL")
    if _llm_base_url(cfg) is None:
        raise RuntimeError(
            f"cascade: provider {_rewrite_provider(cfg)!r} requires LLM_BASE_URL"
        )

    demo_by_urn: dict[str, list[dict[str, Any]]] = {}
    for rem in demo:
        demo_by_urn.setdefault(rem["urn"], []).append(rem)

    out: list[dict[str, Any]] = []
    used_llm = False
    for urn in _all_downstream_urns(catalog, source_urn, changes):
        fallback = demo_by_urn.get(urn) or []
        model_path = _model_path_for_urn(urn, models_dir, files)
        model_sql = model_path.read_text() if model_path else None
        allowed = _allowed_columns(catalog, urn, changes)
        ds = catalog.get("datasets_by_urn", {}).get(urn, {})
        schema_fields = [f["name"] for f in ds.get("schema_fields", [])]
        downstream_info = [{"urn": urn, "schema_fields": schema_fields}]

        llm, meta = _call_llm(changes, downstream_info, model_sql, cfg)
        if llm is None:
            _log_agent(
                f"agent=deterministic fallback urn={urn} "
                f"model={meta.get('model')} latency_ms={meta.get('latency_ms')} "
                f"reason={meta.get('error') or 'llm_failed'}"
            )
            out.extend(fallback)
            continue

        try:
            rem = _rem_from_llm(
                urn, llm, model_path=model_path, allowed=allowed, changes=changes
            )
        except ValueError:
            _log_agent(
                f"agent=deterministic fallback urn={urn} "
                f"model={meta.get('model')} latency_ms={meta.get('latency_ms')} "
                f"reason=schema_gate"
            )
            out.extend(fallback)
            continue

        if rem is None:
            _log_agent(
                f"agent=deterministic fallback urn={urn} "
                f"model={meta.get('model')} latency_ms={meta.get('latency_ms')} "
                f"reason=bad_llm_payload"
            )
            out.extend(fallback)
            continue

        used_llm = True
        _log_agent(
            f"agent=llm urn={urn} strategy={rem['strategy']} "
            f"model={meta.get('model')} latency_ms={meta.get('latency_ms')}"
        )
        out.append(rem)

    if not out:
        _log_agent("agent=deterministic reason=llm_empty")
        return demo
    if not used_llm:
        _log_agent("agent=deterministic reason=all_nodes_fell_back")
    return out
