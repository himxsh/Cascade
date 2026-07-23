from __future__ import annotations

from typing import Any

from cascade.datahub_fixture import get_downstream_lineage, get_ml_impact, load_catalog
from cascade.models import ImpactReport


def build_impact_report(
    source_urn: str,
    changes: list[dict[str, Any]],
    fixture_path: str | None = None,
    catalog: dict[str, Any] | None = None,
) -> ImpactReport:
    if catalog is None:
        catalog = load_catalog(fixture_path)

    changed_field_names = set()
    for c in changes:
        if c["type"] in ("FIELD_REMOVED", "FIELD_RENAMED"):
            if c.get("from"):
                changed_field_names.add(c["from"])
        elif c["type"] == "FIELD_TYPE_CHANGED":
            changed_field_names.add(c.get("from") or c.get("field", ""))

    downstream_urns = get_downstream_lineage(source_urn, catalog)
    blast_radius = {source_urn} | set(downstream_urns)

    downstream_nodes = []
    for urn in downstream_urns:
        ds = catalog["datasets_by_urn"].get(urn)
        if ds:
            downstream_nodes.append({
                "urn": urn,
                "type": "dataset",
                "owners": ds.get("owners", []),
            })

    has_breaking = any(c["type"] in ("FIELD_REMOVED", "FIELD_RENAMED") for c in changes)

    # ponytail: simple severity heuristic — high if a breaking change hits real downstream nodes
    severity: str = "low"
    if has_breaking and downstream_nodes:
        severity = "high"
    elif has_breaking:
        severity = "medium"

    ml_impact = get_ml_impact(changed_field_names, blast_radius, catalog)

    return ImpactReport(
        source_urn=source_urn,
        changes=changes,
        downstream=downstream_nodes,
        ml_impact=ml_impact,
        severity=severity,
    )
