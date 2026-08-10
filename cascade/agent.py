"""Agent: choose remediation strategy + rewrite downstream SQL.

LLM is primary when LLM_API_KEY / OPENAI_API_KEY is set.
Deterministic rewrite is used only when:
  - no API key
  - LLM transport/parse failure
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

from cascade.config import load_config, resolve_model_path
from cascade.schema_gate import validate_sql
from cascade.rewrite import rename_column

_LLM_CHAT_URL_RE = re.compile(r"^(https?://.+)/chat/completions$")
_DEFAULT_MODEL = "qwen.qwen3-coder-480b-a35b-v1:0"
_DEFAULT_BASE_URL = "https://bedrock-mantle.us-east-1.api.aws/v1"
_DEFAULT_TIMEOUT_SEC = 15
_DEFAULT_MAX_LATENCY_MS = 15_000


def _llm_timeout_sec() -> float:
    raw = os.environ.get("LLM_TIMEOUT_SEC", "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return float(_DEFAULT_TIMEOUT_SEC)


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


def _get_new_column_names(changes: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for c in changes:
        to = c.get("to")
        if to:
            names.add(to)
    return names


def _all_downstream_urns(catalog: dict[str, Any], source_urn: str | None) -> list[str]:
    downstream_map = catalog.get("downstream_map", {})
    all_downstream: list[str] = []
    seen: set[str] = set()
    queue = list(downstream_map.get(source_urn or "", []))
    for urn in queue:
        if urn not in seen:
            seen.add(urn)
            all_downstream.append(urn)
    while queue:
        current = queue.pop(0)
        for child in downstream_map.get(current, []):
            if child not in seen:
                seen.add(child)
                all_downstream.append(child)
                queue.append(child)
    return all_downstream


def _allowed_columns(
    catalog: dict[str, Any], urn: str, changes: list[dict[str, Any]]
) -> set[str]:
    datasets_by_urn = catalog.get("datasets_by_urn", {})
    ds = datasets_by_urn.get(urn, {})
    schema_fields = {f["name"] for f in ds.get("schema_fields", [])}
    all_catalog_cols: set[str] = set()
    for d in datasets_by_urn.values():
        for f in d.get("schema_fields", []):
            all_catalog_cols.add(f["name"])
    return schema_fields | _get_new_column_names(changes) | all_catalog_cols


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

    all_downstream = _all_downstream_urns(catalog, source_urn)
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
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Returns (parsed_json_or_None, meta). Meta never includes secrets."""
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("LLM_MODEL", _DEFAULT_MODEL)
    meta: dict[str, Any] = {"model": model, "latency_ms": None, "ok": False, "error": None}
    if not api_key:
        meta["error"] = "no_api_key"
        return None, meta

    prompt = (
        "You are a schema migration assistant. Given a schema change and a downstream "
        "model SQL file, select a remediation strategy and produce rewritten SQL.\n\n"
        "Return JSON with keys: strategy (one of rewrite, adapter_view, deprecate), "
        "rationale (one-line why), sql (rewritten SQL if strategy is rewrite, else null).\n\n"
        f"Changes: {json.dumps(changes)}\n"
        f"Downstream info: {json.dumps(downstream_info)}\n"
    )
    if model_sql is not None:
        prompt += f"Model SQL:\n{model_sql}\n"

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
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
) -> dict[str, Any] | None:
    strategy = llm.get("strategy")
    if strategy not in ("rewrite", "adapter_view", "deprecate"):
        return None
    rationale = (llm.get("rationale") or "").strip() or "LLM remediation"
    if strategy == "rewrite":
        rewritten = llm.get("sql")
        if not rewritten or not model_path:
            return None
        validate_sql(rewritten, allowed)  # raises ValueError → caller falls back
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


# ponytail: OpenAI-compatible HTTP; default = Bedrock Mantle Qwen via LLM_BASE_URL + LLM_MODEL
def choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None = None,
    source_urn: str | None = None,
    urn_files: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """LLM-primary remediations when keyed; deterministic only as fallback."""
    files = urn_files if urn_files is not None else load_config().urn_files
    demo = _demo_choose_and_rewrite(changes, catalog, models_dir, source_urn, files)
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        _log_agent("agent=deterministic reason=no_api_key")
        return demo

    demo_by_urn: dict[str, list[dict[str, Any]]] = {}
    for rem in demo:
        demo_by_urn.setdefault(rem["urn"], []).append(rem)

    out: list[dict[str, Any]] = []
    used_llm = False
    for urn in _all_downstream_urns(catalog, source_urn):
        fallback = demo_by_urn.get(urn) or []
        model_path = _model_path_for_urn(urn, models_dir, files)
        model_sql = model_path.read_text() if model_path else None
        allowed = _allowed_columns(catalog, urn, changes)
        ds = catalog.get("datasets_by_urn", {}).get(urn, {})
        schema_fields = [f["name"] for f in ds.get("schema_fields", [])]
        downstream_info = [{"urn": urn, "schema_fields": schema_fields}]

        llm, meta = _call_llm(changes, downstream_info, model_sql)
        if llm is None:
            _log_agent(
                f"agent=deterministic fallback urn={urn} "
                f"model={meta.get('model')} latency_ms={meta.get('latency_ms')} "
                f"reason={meta.get('error') or 'llm_failed'}"
            )
            out.extend(fallback)
            continue

        try:
            rem = _rem_from_llm(urn, llm, model_path=model_path, allowed=allowed)
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
