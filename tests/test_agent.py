import contextlib
import io
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

from cascade.agent import _call_llm, choose_and_rewrite
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


class TestLlmTransport(unittest.TestCase):
    def test_requests_strict_remediation_schema(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps({
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "strategy": "deprecate",
                        "rationale": "test",
                        "sql": None,
                    })
                }
            }]
        }).encode()
        response.__enter__.return_value = response

        with mock.patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MODEL": "test-model", "CASCADE_MODE": "llm"}, clear=False):
            with mock.patch("cascade.agent.urlopen", return_value=response) as urlopen:
                parsed, meta = _call_llm([], [], None)

        request = urlopen.call_args.args[0]
        response_format = json.loads(request.data)["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])
        self.assertEqual(
            response_format["json_schema"]["schema"]["required"],
            ["strategy", "rationale", "sql"],
        )
        self.assertEqual(parsed["strategy"], "deprecate")
        self.assertTrue(meta["ok"])


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

    def test_ignores_line_comments(self):
        sql = "-- Staging: clean raw orders for downstream marts.\nSELECT customer_id FROM t"
        validate_sql(sql, {"customer_id"})

    def test_ignores_three_part_table_name(self):
        sql = "SELECT customer_id FROM analytics.public.raw_orders"
        validate_sql(sql, {"customer_id"})

    def test_ignores_as_alias(self):
        sql = "SELECT customer_id AS customer_key FROM analytics.public.stg_orders"
        validate_sql(sql, {"customer_id"})

    def test_rejects_invented_qualified_column(self):
        sql = "SELECT i.line_amount_usd_cents FROM stg_order_items i"
        with self.assertRaises(ValueError):
            validate_sql(sql, {"line_amount_cents", "order_id"})

    def test_passes_qualified_allowed_column(self):
        sql = "SELECT i.line_amount_cents FROM stg_order_items i"
        validate_sql(sql, {"line_amount_cents"})


class TestRenameSemantics(unittest.TestCase):
    def test_rejects_wrong_direction_alias(self):
        from cascade.schema_gate import validate_rename_semantics

        changes = [{"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id"}]
        with self.assertRaises(ValueError):
            validate_rename_semantics(
                "SELECT user_id AS customer_id FROM raw_orders", changes
            )

    def test_allows_compat_alias(self):
        from cascade.schema_gate import validate_rename_semantics

        changes = [{"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id"}]
        validate_rename_semantics(
            "SELECT customer_id AS user_id FROM raw_orders", changes
        )

    def test_rejects_unrelated_alias_to_rename_target(self):
        from cascade.schema_gate import validate_rename_semantics

        changes = [
            {"type": "FIELD_RENAMED", "from": "amount_cents", "to": "amount_usd_cents"}
        ]
        with self.assertRaises(ValueError):
            validate_rename_semantics(
                "SELECT i.line_amount_cents AS amount_usd_cents FROM items i",
                changes,
            )


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
            rewrite_mode="deterministic",
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
            rewrite_mode="deterministic",
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
            rewrite_mode="deterministic",
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
            rewrite_mode="deterministic",
        )
        self.assertGreater(len(remediations), 0)
        self.assertTrue(all(r.get("agent") == "deterministic" for r in remediations))

    def test_llm_mode_without_key_raises(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        env = {k: v for k, v in os.environ.items() if k not in ("LLM_API_KEY", "OPENAI_API_KEY")}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError):
                choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                    rewrite_mode="llm",
                )

    def test_deterministic_mode_skips_llm_when_keyed(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MODEL": "x"}, clear=False):
            with mock.patch("cascade.agent._call_llm") as call:
                remediations = choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                    rewrite_mode="deterministic",
                )
        call.assert_not_called()
        self.assertTrue(all(r.get("agent") == "deterministic" for r in remediations))


class TestLlmPrimary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(FIXTURE)

    def test_llm_owns_rewrite_when_keyed(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        llm_sql = (MODELS_DIR / "fct_orders.sql").read_text().replace("user_id", "customer_id")
        fake = {
            "strategy": "rewrite",
            "rationale": "LLM: rename user_id to customer_id in fct_orders",
            "sql": llm_sql,
        }
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MODEL": "test-model", "CASCADE_MODE": "llm"}, clear=False):
            with mock.patch("cascade.agent._call_llm", return_value=(fake, {
                "model": "qwen.qwen3-coder-480b-a35b-v1:0", "latency_ms": 12, "ok": True, "error": None,
            })):
                remediations = choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                )
        fct = next(r for r in remediations if r.get("urn") == FCT_URN and r["strategy"] == "rewrite")
        self.assertEqual(fct["agent"], "llm")
        self.assertIn("LLM:", fct["rationale"])
        self.assertIn("customer_id", fct["rewritten_sql"])

    def test_llm_schema_gate_falls_back(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        fake = {
            "strategy": "rewrite",
            "rationale": "bad invent",
            "sql": "SELECT totally_invented_col FROM t",
        }
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MODEL": "test-model", "CASCADE_MODE": "llm"}, clear=False):
            with mock.patch("cascade.agent._call_llm", return_value=(fake, {
                "model": "qwen.qwen3-coder-480b-a35b-v1:0", "latency_ms": 5, "ok": True, "error": None,
            })):
                remediations = choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                )
        fct = next(r for r in remediations if r.get("urn") == FCT_URN and r["strategy"] == "rewrite")
        self.assertEqual(fct["agent"], "deterministic")
        self.assertIn("customer_id", fct["rewritten_sql"])

    def test_llm_timeout_falls_back(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        with mock.patch.dict(os.environ, {"LLM_API_KEY": "test-key", "LLM_MODEL": "test-model", "CASCADE_MODE": "llm"}, clear=False):
            with mock.patch("cascade.agent._call_llm", return_value=(None, {
                "model": "qwen.qwen3-coder-480b-a35b-v1:0", "latency_ms": 30000, "ok": False, "error": "TimeoutError",
            })):
                remediations = choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                )
        self.assertTrue(all(r.get("agent") == "deterministic" for r in remediations))
        self.assertTrue(any(r["strategy"] == "rewrite" for r in remediations))

    def test_llm_high_latency_falls_back(self):
        changes = [
            {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id",
             "detected_by": "heuristic"}
        ]
        with mock.patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "test-key",
                "LLM_MODEL": "test-model",
                "CASCADE_MODE": "llm",
                "LLM_MAX_LATENCY_MS": "1000",
            },
            clear=False,
        ):
            with mock.patch("cascade.agent._call_llm", return_value=(None, {
                "model": "qwen.qwen3-coder-480b-a35b-v1:0", "latency_ms": 16000, "ok": False, "error": "latency_budget",
            })):
                remediations = choose_and_rewrite(
                    changes=changes,
                    catalog=self.catalog,
                    models_dir=str(MODELS_DIR),
                    source_urn=RAW_URN,
                )
        self.assertTrue(all(r.get("agent") == "deterministic" for r in remediations))
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
