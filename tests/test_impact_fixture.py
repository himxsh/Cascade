import json
import unittest
from pathlib import Path

from cascade.datahub_fixture import (
    get_downstream_lineage,
    get_ml_impact,
    get_owners,
    get_schema_fields,
    load_catalog,
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


if __name__ == "__main__":
    unittest.main()
