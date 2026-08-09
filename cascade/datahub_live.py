from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any

from cascade.datahub_fixture import load_catalog


def _gms_url() -> str:
    return os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")


def _gms_token() -> str | None:
    return os.environ.get("DATAHUB_TOKEN") or None


def health_check(url: str | None = None) -> bool:
    url = (url or _gms_url()).rstrip("/")
    try:
        req = urllib.request.Request(f"{url}/health", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _graphql(
    url: str,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    gql_url = f"{url.rstrip('/')}/api/graphql"
    req = urllib.request.Request(gql_url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    if "errors" in data:
        raise ValueError(f"GraphQL error: {data['errors']}")
    return data


GET_DATASET = """query getDataset($urn: String!) {
  dataset(urn: $urn) {
    urn
    properties { name description }
    schemaMetadata {
      fields { fieldPath nativeDataType }
    }
    ownership {
      owners {
        owner {
          ... on CorpUser { urn }
          ... on CorpGroup { urn }
        }
      }
    }
  }
}"""

GET_LINEAGE = """query getLineage($urn: String!, $direction: LineageDirection!, $start: Int, $count: Int) {
  searchAcrossLineage(input: {
    urn: $urn
    direction: $direction
    query: "*"
    start: $start
    count: $count
    orFilters: [{ and: [{ field: "degree", values: ["1"], condition: EQUAL }] }]
  }) {
    total
    searchResults {
      degree
      entity { urn type }
    }
  }
}"""

GET_ML_MODEL = """query getMlModel($urn: String!) {
  mlModel(urn: $urn) {
    urn
    properties { name description }
  }
}"""


def fetch_dataset(
    urn: str, gms_url: str | None = None, token: str | None = None
) -> dict[str, Any] | None:
    url = gms_url or _gms_url()
    tok = token or _gms_token()
    result = _graphql(url, GET_DATASET, {"urn": urn}, tok)
    data = result.get("data", {}).get("dataset")
    if not data:
        return None
    fields = [
        {"name": f["fieldPath"], "type": f.get("nativeDataType", "unknown")}
        for f in (data.get("schemaMetadata") or {}).get("fields", [])
    ]
    owners = [
        o["owner"]["urn"]
        for o in (data.get("ownership") or {}).get("owners", [])
        if o.get("owner", {}).get("urn")
    ]
    props = data.get("properties") or {}
    return {
        "urn": urn,
        "name": props.get("name", urn),
        "schema_fields": fields,
        "owners": owners,
    }


def fetch_downstream_lineage(
    urn: str, gms_url: str | None = None, token: str | None = None
) -> list[str]:
    """One-hop downstream URNs via searchAcrossLineage (DataHub 1.x GraphQL)."""
    url = gms_url or _gms_url()
    tok = token or _gms_token()
    urns: list[str] = []
    start = 0
    count = 100
    while True:
        result = _graphql(
            url, GET_LINEAGE, {"urn": urn, "direction": "DOWNSTREAM", "start": start, "count": count}, tok
        )
        page = result.get("data", {}).get("searchAcrossLineage") or {}
        hits = page.get("searchResults") or []
        if not hits:
            break
        for hit in hits:
            entity = hit.get("entity") or {}
            child = entity.get("urn")
            if child:
                urns.append(child)
        if start + len(hits) >= (page.get("total") or 0) or len(hits) < count:
            break
        start += count
    return urns


def fetch_ml_model(
    urn: str, gms_url: str | None = None, token: str | None = None
) -> dict[str, Any] | None:
    url = gms_url or _gms_url()
    tok = token or _gms_token()
    try:
        result = _graphql(url, GET_ML_MODEL, {"urn": urn}, tok)
    except Exception:
        return None
    data = result.get("data", {}).get("mlModel")
    if not data:
        return None
    props = data.get("properties") or {}
    return {
        "urn": urn,
        "name": props.get("name", urn),
        "description": props.get("description") or "",
    }


def _hydrate_ml_from_fixture(
    catalog: dict[str, Any],
    fixture_path: str | Path | None,
    *,
    reason: str,
) -> None:
    print(f"cascade: ML from fixture ({reason})", file=sys.stderr)
    try:
        fc = load_catalog(fixture_path)
        for k in ("ml_features_by_name", "ml_models_by_feature_urn", "all_ml_features", "all_ml_models"):
            catalog[k] = fc[k]
    except Exception as e:
        print(f"cascade: fixture ML fallback failed: {e}", file=sys.stderr)


def _try_live_ml(
    catalog: dict[str, Any],
    fixture_path: str | Path | None,
    gms_url: str,
    token: str | None,
) -> None:
    """Prefer GMS ML entities when seeded; else fixture with stderr notice."""
    try:
        fc = load_catalog(fixture_path)
    except Exception:
        return

    live_models: list[dict[str, Any]] = []
    for mm in fc.get("all_ml_models") or []:
        urn = mm.get("urn")
        if not urn:
            continue
        got = fetch_ml_model(urn, gms_url, token)
        if got:
            live_models.append({**mm, **got})

    if not live_models:
        _hydrate_ml_from_fixture(
            catalog, fixture_path, reason="no mlModel aspects in GMS"
        )
        return

    print("cascade: ML models from live GMS", file=sys.stderr)
    catalog["all_ml_models"] = live_models
    catalog["all_ml_features"] = fc.get("all_ml_features") or []
    catalog["ml_features_by_name"] = fc.get("ml_features_by_name") or {}
    catalog["ml_models_by_feature_urn"] = fc.get("ml_models_by_feature_urn") or {}


# ponytail: GraphQL REST stand-in for MCP reads; optional MCP in Phase 6.
#
# Live hydrates datasets + lineage + owners from GMS. ML models are read from
# GMS when present; otherwise fixture ML with an explicit stderr notice.
def load_catalog_live(
    seed_urn: str,
    gms_url: str | None = None,
    token: str | None = None,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    url = gms_url or _gms_url()
    tok = token or _gms_token()

    all_urns: set[str] = set()
    queue: deque[str] = deque([seed_urn])
    ordered: list[str] = []
    dm: dict[str, list[str]] = {}

    while queue:
        current = queue.popleft()
        if current in all_urns:
            continue
        all_urns.add(current)
        ordered.append(current)
        children = fetch_downstream_lineage(current, url, tok)
        if children:
            dm[current] = children
            for child in children:
                if child not in all_urns:
                    queue.append(child)

    datasets_by_urn: dict[str, dict[str, Any]] = {}
    for urn in ordered:
        ds = fetch_dataset(urn, url, tok)
        if ds:
            datasets_by_urn[urn] = ds

    catalog: dict[str, Any] = {
        "datasets_by_urn": datasets_by_urn,
        "downstream_map": dm,
        "ml_features_by_name": {},
        "ml_models_by_feature_urn": {},
        "all_ml_features": [],
        "all_ml_models": [],
        "_raw": {},
    }

    _try_live_ml(catalog, fixture_path, url, tok)
    return catalog


def resolve_catalog(
    source: str,
    seed_urn: str | None = None,
    fixture_path: str | Path | None = None,
) -> dict[str, Any]:
    if source == "live":
        if not health_check():
            print(
                "cascade: DataHub GMS unhealthy at",
                _gms_url(),
                file=sys.stderr,
            )
            sys.exit(1)
        return load_catalog_live(
            seed_urn=seed_urn, fixture_path=fixture_path
        )
    if source == "auto":
        if health_check():
            print("cascade: using live DataHub GMS", file=sys.stderr)
            return load_catalog_live(
                seed_urn=seed_urn, fixture_path=fixture_path
            )
        print("cascade: DataHub GMS unavailable; using fixture", file=sys.stderr)
        return load_catalog(fixture_path)
    return load_catalog(fixture_path)
