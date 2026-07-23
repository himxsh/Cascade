import contextlib
import io
import json
import shutil
import unittest
from pathlib import Path

from cascade.agent import choose_and_rewrite
from cascade.cli import cmd_generate
from cascade.datahub_fixture import load_catalog
from cascade.rewrite import rename_column
from cascade.schema_gate import validate_sql
from cascade.impact import build_impact_report

FIXTURE = Path(__file__).resolve().parents[1] / "demo" / "fixtures" / "demo_graph.json"
MODELS_DIR = Path(__file__).resolve().parents[1] / "examples" / "models"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"
FCT_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)"


class TestRewrite(unittest.TestCase):
    def test_rename_column_replaces_user_id(self):
        sql = "SELECT o.user_id, o.amount FROM raw_orders o"
        result = rename_column(sql, "user_id", "customer_id")
        self.assertEqual(result, "SELECT o.customer_id, o.amount FROM raw_orders o")

    def test_rename_column_word_boundary(self):
        sql = "SELECT user_id, user_id_new FROM t"
        result = rename_column(sql, "user_id", "customer_id")
        self.assertEqual(result, "SELECT customer_id, user_id_new FROM t")

    def test_rename_column_fct_orders(self):
        sql = (Path(__file__).resolve().parents[1] / "examples" / "models" / "fct_orders.sql").read_text()
        result = rename_column(sql, "user_id", "customer_id")
        self.assertIn("customer_id", result)
        self.assertNotIn("user_id", result)


class TestSchemaGate(unittest.TestCase):
    def test_rejects_invented_column(self):
        sql = "SELECT made_up_col FROM t"
        allowed = {"order_id", "amount"}
        with self.assertRaises(ValueError):
            validate_sql(sql, allowed)

    def test_passes_all_columns_allowed(self):
        sql = "SELECT order_id, amount FROM t"
        allowed = {"order_id", "amount"}
        validate_sql(sql, allowed)

    def test_passes_with_extra_allowed(self):
        sql = "SELECT customer_id FROM t"
        allowed = {"order_id", "amount", "customer_id"}
        validate_sql(sql, allowed)


class TestDemoAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(FIXTURE)

    def test_returns_rewrite_for_fct_orders(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=self.catalog,
            models_dir=str(MODELS_DIR),
            source_urn=RAW_URN,
        )
        fct_rems = [r for r in remediations if FCT_URN in r.get("urn", "")]
        self.assertGreaterEqual(len(fct_rems), 1)
        rewrite_rem = next((r for r in fct_rems if r["strategy"] == "rewrite"), None)
        self.assertIsNotNone(rewrite_rem)
        self.assertIn("rewritten_sql", rewrite_rem)
        self.assertIn("customer_id", rewrite_rem["rewritten_sql"])
        self.assertNotIn("user_id", rewrite_rem["rewritten_sql"])
        self.assertTrue(len(rewrite_rem["rationale"]) > 0)

    def test_demo_agent_rationale_nonempty(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=self.catalog,
            models_dir=str(MODELS_DIR),
            source_urn=RAW_URN,
        )
        for rem in remediations:
            self.assertTrue(len(rem["rationale"]) > 0, f"empty rationale for {rem}")

    def test_has_adapter_view_for_urns_without_model(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=self.catalog,
            models_dir=str(MODELS_DIR),
            source_urn=RAW_URN,
        )
        strategies = {r["strategy"] for r in remediations}
        self.assertIn("adapter_view", strategies)

    def test_no_api_key_uses_demo(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=self.catalog,
            models_dir=str(MODELS_DIR),
            source_urn=RAW_URN,
        )
        self.assertGreater(len(remediations), 0)


class TestGenerateCLI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/_cascade_test_gen")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_generate_writes_file(self):
        report_data = {
            "source_urn": RAW_URN,
            "changes": [
                {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
                 "detected_by": "heuristic"}
            ],
            "downstream": [],
            "ml_impact": [],
            "severity": "high",
        }
        report_path = self.tmp_dir / "report.json"
        report_path.write_text(json.dumps(report_data))
        out_dir = self.tmp_dir / "out"
        args = type("Args", (), {
            "report": str(report_path),
            "out": str(out_dir),
            "models_dir": str(MODELS_DIR),
            "fixture": str(FIXTURE),
            "func": cmd_generate,
        })()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_generate(args)
        self.assertTrue((out_dir / "fct_orders.sql").exists())
        self.assertTrue((out_dir / "impact_report.json").exists())
        rewritten = (out_dir / "fct_orders.sql").read_text()
        self.assertIn("customer_id", rewritten)
        self.assertNotIn("user_id", rewritten)


if __name__ == "__main__":
    unittest.main()
