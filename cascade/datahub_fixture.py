from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any


def _default_fixture_path() -> Path | None:
    """Dev-tree fixture only. The installed wheel does not ship demo/fixtures."""
    env = os.environ.get("CASCADE_FIXTURE_PATH", "").strip()
    if env:
        return Path(env)
    cwd = Path.cwd() / "demo" / "fixtures" / "demo_graph.json"
    if cwd.is_file():
        return cwd
    # Editable checkout: cascade/../demo/fixtures — missing after pip install from PyPI.
    bundled = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "demo_graph.json"
    if bundled.is_file():
        return bundled
    return None


def schema_field_urn(dataset_urn: str, field: str) -> str:
    return f"urn:li:schemaField:({dataset_urn},{field})"


def parse_schema_field_urn(urn: str) -> tuple[str, str] | None:
    prefix = "urn:li:schemaField:("
    if not urn.startswith(prefix) or not urn.endswith(")"):
        return None
    inner = urn[len(prefix) : -1]
    depth = 0
    for i, ch in enumerate(inner):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                rest = inner[i + 1 :]
                if rest.startswith(","):
                    return inner[: i + 1], rest[1:]
                return None
    return None


def lineage_dataset_urn(urn: str) -> str | None:
    if urn.startswith("urn:li:dataset:"):
        return urn
    parsed = parse_schema_field_urn(urn)
    return parsed[0] if parsed else None


def fields_from_changes(changes: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for c in changes:
        kind = c.get("type")
        if kind in ("FIELD_REMOVED", "FIELD_RENAMED") and c.get("from"):
            names.add(str(c["from"]))
        elif kind == "FIELD_TYPE_CHANGED":
            names.add(str(c.get("from") or c.get("field") or ""))
    names.discard("")
    return names


def edges_from_fine_grained(lineages: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    def _ref(ref: dict[str, Any]) -> tuple[str, str] | None:
        urn = str(ref.get("urn") or "")
        path = str(ref.get("path") or "")
        parsed = parse_schema_field_urn(urn)
        if parsed:
            return parsed[0], parsed[1] or path
        ds = lineage_dataset_urn(urn)
        if ds and path:
            return ds, path
        return None

    edges: list[dict[str, str]] = []
    for lin in lineages or []:
        for up in lin.get("upstreams") or []:
            src = _ref(up)
            if not src:
                continue
            for down in lin.get("downstreams") or []:
                tgt = _ref(down)
                if not tgt:
                    continue
                edges.append({
                    "source": src[0],
                    "field": src[1],
                    "target": tgt[0],
                    "target_field": tgt[1] or src[1],
                })
    return edges


def _column_edges_from_raw(data: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for e in data.get("column_lineage") or []:
        src, field, tgt = e.get("source"), e.get("field"), e.get("target")
        if src and field and tgt:
            out.append({
                "source": str(src),
                "field": str(field),
                "target": str(tgt),
                "target_field": str(e.get("target_field") or field),
            })
    return out


def _column_index(
    catalog: dict[str, Any],
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    idx: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for e in catalog.get("column_edges") or []:
        key = (e["source"], e["field"].lower())
        idx.setdefault(key, []).append(
            (e["target"], (e.get("target_field") or e["field"]).lower())
        )
    return idx


def _column_consumers(
    source_urn: str, fields: set[str], catalog: dict[str, Any]
) -> dict[str, set[str]]:
    idx = _column_index(catalog)
    per_field: dict[str, set[str]] = {}
    for field in fields:
        found: set[str] = set()
        queue: deque[tuple[str, str]] = deque([(source_urn, field.lower())])
        seen: set[tuple[str, str]] = set()
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            for tgt, tf in idx.get(node, []):
                found.add(tgt)
                queue.append((tgt, tf))
        per_field[field] = found
    return per_field


def load_catalog(fixture_path: str | Path | None = None) -> dict[str, Any]:
    path = fixture_path or os.environ.get("CASCADE_FIXTURE_PATH") or _default_fixture_path()
    if path is None or not Path(path).is_file():
        raise FileNotFoundError(
            "cascade: fixture catalog not found. Pass --fixture or set "
            "CASCADE_FIXTURE_PATH. The installed package does not ship demo fixtures."
        )
    with open(path) as f:
        data = json.load(f)

    datasets_by_urn: dict[str, dict[str, Any]] = {}
    for ds in data.get("datasets", []):
        datasets_by_urn[ds["urn"]] = ds

    downstream_map: dict[str, list[str]] = {}
    for edge in data.get("lineage", []):
        downstream_map.setdefault(edge["source"], []).append(edge["target"])

    ml_features_by_name: dict[str, dict[str, Any]] = {}
    for mf in data.get("mlFeatures", []):
        ml_features_by_name[mf["name"]] = mf

    ml_models_by_feature_urn: dict[str, list[dict[str, Any]]] = {}
    for mm in data.get("mlModels", []):
        for f_urn in mm.get("features", []):
            ml_models_by_feature_urn.setdefault(f_urn, []).append(mm)

    return {
        "datasets_by_urn": datasets_by_urn,
        "downstream_map": downstream_map,
        "column_edges": _column_edges_from_raw(data),
        "ml_features_by_name": ml_features_by_name,
        "ml_models_by_feature_urn": ml_models_by_feature_urn,
        "all_ml_features": data.get("mlFeatures", []),
        "all_ml_models": data.get("mlModels", []),
        "_raw": data,
    }


def get_schema_fields(urn: str, catalog: dict[str, Any]) -> list[dict[str, Any]]:
    ds = catalog["datasets_by_urn"].get(urn)
    return ds.get("schema_fields", []) if ds else []


def get_owners(urn: str, catalog: dict[str, Any]) -> list[str]:
    ds = catalog["datasets_by_urn"].get(urn)
    if ds:
        return ds.get("owners", [])
    for mf in catalog["all_ml_features"]:
        if mf["urn"] == urn:
            return mf.get("owners", [])
    for mm in catalog["all_ml_models"]:
        if mm["urn"] == urn:
            return mm.get("owners", [])
    return []


def get_downstream_lineage(
    urn: str,
    catalog: dict[str, Any],
    fields: set[str] | None = None,
) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    queue: deque[str] = deque()
    dm = catalog["downstream_map"]

    if urn in dm:
        for child in dm[urn]:
            if child not in seen:
                seen.add(child)
                ordered.append(child)
                queue.append(child)

    while queue:
        current = queue.popleft()
        if current in dm:
            for child in dm[current]:
                if child not in seen:
                    seen.add(child)
                    ordered.append(child)
                    queue.append(child)

    # ponytail: empty column lineage = missing graph, not "no impact" — fall back to tables.
    if not fields:
        return ordered
    per_field = _column_consumers(urn, fields, catalog)
    if not per_field or any(not hits for hits in per_field.values()):
        return ordered
    keep = set().union(*per_field.values())
    return [u for u in ordered if u in keep]


def get_ml_impact(
    changed_field_names: set[str],
    blast_radius_urns: set[str],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for mf in catalog["all_ml_features"]:
        if mf["name"] not in changed_field_names:
            continue
        mf_sources = set(mf.get("sources", []))
        if not mf_sources.intersection(blast_radius_urns):
            continue
        mm_list = catalog["ml_models_by_feature_urn"].get(mf["urn"], [])
        for mm in mm_list:
            result.append({
                "model_urn": mm["urn"],
                "via_feature": mf["name"],
                "action": "retrain-suggested",
            })
    return result
