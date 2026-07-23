from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from cascade.schema_gate import validate_sql
from cascade.rewrite import rename_column


_LLM_CHAT_URL_RE = re.compile(r'^(https?://.+)/chat/completions$')


def _model_path_for_urn(urn: str, models_dir: str | Path) -> Path | None:
    parts = urn.split(",")
    if len(parts) < 2:
        return None
    name = parts[1].rstrip(")")
    stem = name.split(".")[-1]
    p = Path(models_dir) / f"{stem}.sql"
    return p if p.exists() else None


def _get_new_column_names(changes: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for c in changes:
        to = c.get("to")
        if to:
            names.add(to)
    return names


def _demo_choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None,
    source_urn: str | None,
) -> list[dict[str, Any]]:
    remediations: list[dict[str, Any]] = []
    downstream_map = catalog.get("downstream_map", {})
    datasets_by_urn = catalog.get("datasets_by_urn", {})

    renames: dict[str, str] = {}
    has_field_removed = any(c["type"] == "FIELD_REMOVED" and not c.get("to") for c in changes)
    for c in changes:
        if c["type"] == "FIELD_RENAMED" and c.get("from") and c.get("to"):
            renames[c["from"]] = c["to"]

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

    new_cols = _get_new_column_names(changes)
    all_catalog_cols: set[str] = set()
    for ds in datasets_by_urn.values():
        for f in ds.get("schema_fields", []):
            all_catalog_cols.add(f["name"])
    handled_urns: set[str] = set()

    for urn in all_downstream:
        ds = datasets_by_urn.get(urn, {})
        schema_fields = {f["name"] for f in ds.get("schema_fields", [])}
        allowed_base = schema_fields | new_cols | all_catalog_cols

        for old_name, new_name in renames.items():
            model_path = _model_path_for_urn(urn, models_dir) if models_dir else None
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
                })
                handled_urns.add(urn)

    return remediations


def _call_llm(
    changes: list[dict[str, Any]],
    downstream_info: list[dict[str, Any]],
    model_sql: str | None,
) -> dict[str, Any] | None:
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    if not api_key:
        return None

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
        "model": "gpt-4o-mini",
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
    try:
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"]
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned.strip())
    except Exception:
        return None


# ponytail: OpenAI-compatible HTTP; swap provider via LLM_BASE_URL
def choose_and_rewrite(
    changes: list[dict[str, Any]],
    catalog: dict[str, Any],
    models_dir: str | Path | None = None,
    source_urn: str | None = None,
) -> list[dict[str, Any]]:
    remediations = _demo_choose_and_rewrite(changes, catalog, models_dir, source_urn)

    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return remediations

    all_downstream: list[str] = []
    downstream_map = catalog.get("downstream_map", {})
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

    new_cols = _get_new_column_names(changes)
    datasets_by_urn = catalog.get("datasets_by_urn", {})
    all_catalog_cols: set[str] = set()
    for ds in datasets_by_urn.values():
        for f in ds.get("schema_fields", []):
            all_catalog_cols.add(f["name"])

    for i, rem in enumerate(remediations):
        if rem["strategy"] != "rewrite":
            continue
        path_str = rem.get("path")
        model_sql = Path(path_str).read_text() if path_str else None
        urn = rem.get("urn", "")
        ds = datasets_by_urn.get(urn, {})
        schema_fields = {f["name"] for f in ds.get("schema_fields", [])}
        allowed_base = schema_fields | new_cols | all_catalog_cols

        downstream_info = [{"urn": urn, "schema_fields": list(schema_fields)}]

        llm_result = _call_llm(changes, downstream_info, model_sql)
        if llm_result is None:
            continue
        strategy = llm_result.get("strategy")
        if strategy == "rewrite":
            rewritten = llm_result.get("sql")
            if rewritten:
                try:
                    validate_sql(rewritten, allowed_base)
                    rem["rewritten_sql"] = rewritten
                    rem["rationale"] = llm_result.get("rationale", rem["rationale"])
                except ValueError:
                    pass

    return remediations
