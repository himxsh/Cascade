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
  lineage(urn: $urn, direction: $direction, start: $start, count: $count) {
    relationships {
      entity {
        urn
        ... on Dataset { properties { name } }
      }
    }
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
    url = gms_url or _gms_url()
    tok = token or _gms_token()
    urns: list[str] = []
    start = 0
    count = 100
    while True:
        result = _graphql(
            url, GET_LINEAGE, {"urn": urn, "direction": "DOWNSTREAM", "start": start, "count": count}, tok
        )
        relationships = result.get("data", {}).get("lineage", {}).get("relationships", [])
        if not relationships:
            break
        for r in relationships:
            entity = r.get("entity", {})
            if entity.get("urn"):
                urns.append(entity["urn"])
        if len(relationships) < count:
            break
        start += count
    return urns


# ponytail: GraphQL REST stand-in for MCP reads; swap to MCP client when write-back lands
#
# Hybrid: live hydrates datasets + lineage + owners from GMS.
# ML features/models still read from fixture because their aspects are
# inconsistently available via the GMS GraphQL schema.
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

    try:
        fc = load_catalog(fixture_path)
        for k in ("ml_features_by_name", "ml_models_by_feature_urn", "all_ml_features", "all_ml_models"):
            catalog[k] = fc[k]
    except Exception:
        pass

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
