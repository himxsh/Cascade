#!/usr/bin/env python3
"""Self-check: validate demo_graph.json without a live DataHub instance.

Exits 0 if all checks pass, non-zero otherwise.
"""

import json
import sys
from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "demo_graph.json"
EXPECTED_DATASET_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)",
]
RAW_URN = EXPECTED_DATASET_URNS[0]
STG_URN = EXPECTED_DATASET_URNS[1]
FCT_URN = EXPECTED_DATASET_URNS[2]
FEATURES_URN = EXPECTED_DATASET_URNS[3]
ML_FEATURE_URN = "urn:li:mlFeature:(analytics.features_orders,user_id)"
ML_MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)"


def die(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    with open(FIXTURE_PATH) as f:
        fixture = json.load(f)

    # 1. All dataset URNs present
    ds_urns = {ds["urn"] for ds in fixture["datasets"]}
    for expected in EXPECTED_DATASET_URNS:
        if expected not in ds_urns:
            die(f"Missing dataset urn: {expected}")

    # 2. Lineage path raw → stg → fct → features
    lineage = fixture.get("lineage", [])
    lineage_map = {e["source"]: e["target"] for e in lineage}
    if lineage_map.get(RAW_URN) != STG_URN:
        die(f"Lineage missing: raw → stg (got {lineage_map.get(RAW_URN)})")
    if lineage_map.get(STG_URN) != FCT_URN:
        die(f"Lineage missing: stg → fct (got {lineage_map.get(STG_URN)})")
    if lineage_map.get(FCT_URN) != FEATURES_URN:
        die(f"Lineage missing: fct → features (got {lineage_map.get(FCT_URN)})")

    # 3. ML feature → model edge present
    mf_urns = {mf["urn"] for mf in fixture.get("mlFeatures", [])}
    mm_urns = {mm["urn"] for mm in fixture.get("mlModels", [])}

    if ML_FEATURE_URN not in mf_urns:
        die(f"Missing ML feature: {ML_FEATURE_URN}")
    if ML_MODEL_URN not in mm_urns:
        die(f"Missing ML model: {ML_MODEL_URN}")

    # Verify the model references the feature
    for mm in fixture.get("mlModels", []):
        if mm["urn"] == ML_MODEL_URN:
            if ML_FEATURE_URN not in mm.get("features", []):
                die(f"ML model {ML_MODEL_URN} does not reference feature {ML_FEATURE_URN}")
            break

    # 4. user_id field on raw and fct
    raw_ds = next(ds for ds in fixture["datasets"] if ds["urn"] == RAW_URN)
    fct_ds = next(ds for ds in fixture["datasets"] if ds["urn"] == FCT_URN)
    raw_field_names = {sf["name"] for sf in raw_ds["schema_fields"]}
    fct_field_names = {sf["name"] for sf in fct_ds["schema_fields"]}

    if "user_id" not in raw_field_names:
        die(f"raw_orders missing user_id field")
    if "user_id" not in fct_field_names:
        die(f"fct_orders missing user_id field")

    # Verify description on raw notes rename target
    if "rename" not in raw_ds.get("description", "").lower():
        die(f"raw_orders description should mention rename")

    # 5. Owners on each dataset
    for ds in fixture["datasets"]:
        if not ds.get("owners"):
            die(f"Dataset {ds['urn']} has no owners")

    print(f"OK: {len(ds_urns)} datasets, {len(lineage)} lineage edges, "
          f"{len(mf_urns)} ML features, {len(mm_urns)} ML models")
    sys.exit(0)


if __name__ == "__main__":
    main()
