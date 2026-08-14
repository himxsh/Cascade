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


def get_downstream_lineage(urn: str, catalog: dict[str, Any]) -> list[str]:
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

    return ordered


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
