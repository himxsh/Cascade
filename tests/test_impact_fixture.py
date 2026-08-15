import json
import unittest
from pathlib import Path

from cascade.agent import choose_and_rewrite
from cascade.datahub_fixture import (
    get_downstream_lineage,
    get_ml_impact,
    get_owners,
    get_schema_fields,
    load_catalog,
    parse_schema_field_urn,
    schema_field_urn,
)
from cascade.impact import build_impact_report

FIXTURE = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "demo_graph.json"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"
STG_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)"
FCT_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)"
FEATURES_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)"
ML_MODEL_URN = "urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)"


class TestImpactFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(FIXTURE)

    def test_schema_fields_on_raw(self):
        fields = get_schema_fields(RAW_URN, self.catalog)
        names = {f["name"] for f in fields}
        self.assertIn("user_id", names)

    def test_downstream_lineage_bfs(self):
        urns = get_downstream_lineage(RAW_URN, self.catalog)
        self.assertIn(STG_URN, urns)
        self.assertIn(FCT_URN, urns)
        self.assertIn(FEATURES_URN, urns)

    def test_owners_on_raw(self):
        owners = get_owners(RAW_URN, self.catalog)
        self.assertIn("urn:li:corpuser:alice", owners)

    def test_full_impact_report_high_severity(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        report = build_impact_report(RAW_URN, changes, fixture_path=str(FIXTURE))
        self.assertEqual(report.severity, "high")
        downstream_urns = {n["urn"] for n in report.downstream}
        self.assertIn(STG_URN, downstream_urns)
        self.assertIn(FCT_URN, downstream_urns)
        self.assertIn(FEATURES_URN, downstream_urns)

    def test_ml_impact_includes_churn_predictor(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        report = build_impact_report(RAW_URN, changes, fixture_path=str(FIXTURE))
        model_urns = [m["model_urn"] for m in report.ml_impact]
        self.assertIn(ML_MODEL_URN, model_urns)
        for m in report.ml_impact:
            if m["model_urn"] == ML_MODEL_URN:
                self.assertEqual(m["action"], "retrain-suggested")
                self.assertEqual(m["via_feature"], "user_id")

    def test_report_to_dict_json_serializable(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        report = build_impact_report(RAW_URN, changes, fixture_path=str(FIXTURE))
        d = report.to_dict()
        json.dumps(d)


class TestColumnLineage(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(FIXTURE)
        self.dim = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.dim_date,PROD)"
        self.catalog["datasets_by_urn"] = dict(self.catalog["datasets_by_urn"])
        self.catalog["datasets_by_urn"][self.dim] = {
            "urn": self.dim,
            "schema_fields": [{"name": "day", "type": "date"}],
            "owners": [],
        }
        dm = {k: list(v) for k, v in self.catalog["downstream_map"].items()}
        dm[RAW_URN] = list(dm[RAW_URN]) + [self.dim]
        self.catalog["downstream_map"] = dm
        self.catalog["column_edges"] = [
            {"source": RAW_URN, "field": "user_id", "target": STG_URN, "target_field": "user_id"},
            {"source": STG_URN, "field": "user_id", "target": FCT_URN, "target_field": "user_id"},
            {"source": FCT_URN, "field": "user_id", "target": FEATURES_URN, "target_field": "user_id"},
        ]

    def test_parse_schema_field_urn(self):
        urn = schema_field_urn(RAW_URN, "user_id")
        self.assertEqual(parse_schema_field_urn(urn), (RAW_URN, "user_id"))

    def test_filters_to_column_consumers(self):
        urns = get_downstream_lineage(RAW_URN, self.catalog, fields={"user_id"})
        self.assertIn(STG_URN, urns)
        self.assertIn(FCT_URN, urns)
        self.assertIn(FEATURES_URN, urns)
        self.assertNotIn(self.dim, urns)

    def test_empty_column_lineage_keeps_table_blast_radius(self):
        self.catalog["column_edges"] = []
        urns = get_downstream_lineage(RAW_URN, self.catalog, fields={"user_id"})
        self.assertIn(self.dim, urns)

    def test_impact_report_drops_unrelated_table(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        report = build_impact_report(RAW_URN, changes, catalog=self.catalog)
        downstream = {n["urn"] for n in report.downstream}
        self.assertNotIn(self.dim, downstream)
        self.assertIn(STG_URN, downstream)

    def test_rewrite_skips_unrelated_table(self):
        remediations = choose_and_rewrite(
            changes=[{"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id"}],
            catalog=self.catalog,
            source_urn=RAW_URN,
            rewrite_mode="deterministic",
        )
        self.assertNotIn(self.dim, {r["urn"] for r in remediations})


if __name__ == "__main__":
    unittest.main()
