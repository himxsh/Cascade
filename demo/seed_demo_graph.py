#!/usr/bin/env python3
"""Seed the demo lineage graph into DataHub.

Usage:
    python demo/seed_demo_graph.py           # dry-run (print what would be emitted)
    python demo/seed_demo_graph.py --apply    # emit to live DataHub GMS

Env:
    DATAHUB_GMS_URL  (default http://localhost:8080)
    DATAHUB_TOKEN    (optional, empty for local)
"""

import json
import os
import sys
from pathlib import Path

try:
    from datahub.emitter.mcp import MetadataChangeProposalWrapper
    from datahub.emitter.rest_emitter import DatahubRestEmitter
    from datahub.metadata.schema_classes import (
        AuditStampClass,
        DatasetLineageTypeClass,
        DatasetPropertiesClass,
        MLFeaturePropertiesClass,
        MLModelPropertiesClass,
        NumberTypeClass,
        OtherSchemaClass,
        OwnerClass,
        OwnershipClass,
        OwnershipTypeClass,
        SchemaFieldClass,
        SchemaFieldDataTypeClass,
        SchemaMetadataClass,
        StringTypeClass,
        UpstreamClass,
        UpstreamLineageClass,
    )
except ImportError:
    print("acryl-datahub SDK required. Install: pip install -r demo/requirements.txt",
          file=sys.stderr)
    sys.exit(1)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "demo_graph.json"


def _ownership_mcp(urn, owner_urns):
    return MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=OwnershipClass(
            owners=[OwnerClass(owner=o, type=OwnershipTypeClass.DATAOWNER) for o in owner_urns],
            lastModified=AuditStampClass(time=0, actor="urn:li:corpuser:datahub"),
        ),
    )


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def build_dataset_mcps(ds):
    urn = ds["urn"]
    mcps = []

    mcps.append(MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=DatasetPropertiesClass(description=ds["description"]),
    ))

    type_map = {"int": NumberTypeClass, "float": NumberTypeClass, "string": StringTypeClass}
    fields = [
        SchemaFieldClass(
            fieldPath=sf["name"],
            type=SchemaFieldDataTypeClass(type=type_map.get(sf["type"], StringTypeClass)()),
            nativeDataType=sf["type"],
        )
        for sf in ds["schema_fields"]
    ]
    mcps.append(MetadataChangeProposalWrapper(
        entityUrn=urn,
        aspect=SchemaMetadataClass(
            schemaName=ds["name"],
            platform="urn:li:dataPlatform:" + ds["platform"],
            version=0,
            hash="",
            platformSchema=OtherSchemaClass(rawSchema=""),
            fields=fields,
        ),
    ))

    mcps.append(_ownership_mcp(urn, ds["owners"]))
    return mcps


def build_lineage_mcps(lineage_list):
    return [
        MetadataChangeProposalWrapper(
            entityUrn=edge["target"],
            aspect=UpstreamLineageClass(upstreams=[
                UpstreamClass(dataset=edge["source"], type=DatasetLineageTypeClass.TRANSFORMED),
            ]),
        )
        for edge in lineage_list
    ]


def build_ml_feature_mcps(mf):
    urn = mf["urn"]
    return [
        MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=MLFeaturePropertiesClass(
                description=mf["description"],
                sources=mf.get("sources", []),
            ),
        ),
        _ownership_mcp(urn, mf["owners"]),
    ]


def build_ml_model_mcps(mm):
    urn = mm["urn"]
    return [
        MetadataChangeProposalWrapper(
            entityUrn=urn,
            aspect=MLModelPropertiesClass(
                description=mm["description"],
                mlFeatures=mm.get("features", []),
            ),
        ),
        _ownership_mcp(urn, mm["owners"]),
    ]


def build_all_mcps(fixture):
    mcps = []
    for ds in fixture["datasets"]:
        mcps.extend(build_dataset_mcps(ds))
    mcps.extend(build_lineage_mcps(fixture.get("lineage", [])))
    for mf in fixture.get("mlFeatures", []):
        mcps.extend(build_ml_feature_mcps(mf))
    for mm in fixture.get("mlModels", []):
        mcps.extend(build_ml_model_mcps(mm))
    return mcps


def dry_run(mcps):
    print(f"[dry-run] Would emit {len(mcps)} MetadataChangeProposal(s):\n")
    for mcp in mcps:
        print(f"  {mcp.entityType:<12} {mcp.entityUrn}")
        print(f"  {'':>12} └── {mcp.aspectName}")
        print()


def apply(mcps, gms_url, token):
    emitter = DatahubRestEmitter(gms_server=gms_url, token=token)
    ok = 0
    for mcp in mcps:
        try:
            emitter.emit(mcp)
            ok += 1
        except Exception as e:
            print(f"  FAIL: {mcp.entityUrn} [{mcp.aspectName}]: {e}", file=sys.stderr)
    print(f"Emitted {ok}/{len(mcps)} MCPs to {gms_url}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed demo lineage graph into DataHub")
    parser.add_argument("--apply", action="store_true", help="Emit to live DataHub GMS")
    args = parser.parse_args()

    fixture = load_fixture()
    mcps = build_all_mcps(fixture)

    if args.apply:
        gms_url = os.environ.get("DATAHUB_GMS_URL", "http://localhost:8080")
        token = os.environ.get("DATAHUB_TOKEN", "")
        apply(mcps, gms_url, token)
    else:
        dry_run(mcps)


if __name__ == "__main__":
    main()
