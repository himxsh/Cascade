"""Golden-diff eval (F11): known rename → expected ImpactReport + rewritten SQL."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from cascade.agent import choose_and_rewrite
from cascade.datahub_fixture import load_catalog
from cascade.diff_parser import load_changes
from cascade.impact import build_impact_report

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / "golden" / "raw_orders_rename"
FIXTURE = "demo/fixtures/demo_graph.json"
MODELS_DIR = "examples/models"
DIFF = "examples/diffs/raw_orders_rename_user_id.json"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"


def _strip_rewritten_sql(remediations: list[dict]) -> list[dict]:
    out = []
    for rem in remediations:
        cleaned = {k: v for k, v in rem.items() if k != "rewritten_sql"}
        out.append(cleaned)
    return out


class TestGoldenDiffEval(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_rewritten_sql_matches_golden(self):
        changes = load_changes(DIFF)
        catalog = load_catalog(FIXTURE)
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=catalog,
            models_dir=MODELS_DIR,
            source_urn=RAW_URN,
        )
        rewrite = next(r for r in remediations if r.get("strategy") == "rewrite")
        expected = (GOLDEN / "expected_fct_orders.sql").read_text()
        self.assertEqual(rewrite["rewritten_sql"], expected)

    def test_impact_report_matches_golden(self):
        changes = load_changes(DIFF)
        catalog = load_catalog(FIXTURE)
        report = build_impact_report(
            source_urn=RAW_URN,
            changes=changes,
            catalog=catalog,
        )
        remediations = choose_and_rewrite(
            changes=changes,
            catalog=catalog,
            models_dir=MODELS_DIR,
            source_urn=RAW_URN,
        )
        report.remediations = remediations
        actual = report.to_dict()
        actual["remediations"] = _strip_rewritten_sql(actual["remediations"])

        expected = json.loads((GOLDEN / "expected_impact_report.json").read_text())
        self.assertEqual(actual, expected)

    def test_examples_headline_matches_golden(self):
        """Static demo artifact under examples/rewritten must stay in sync with golden."""
        headline = (ROOT / "examples" / "rewritten" / "fct_orders.sql").read_text()
        expected = (GOLDEN / "expected_fct_orders.sql").read_text()
        self.assertEqual(headline, expected)
        diff_text = (ROOT / "examples" / "rewritten" / "headline_pr.diff").read_text()
        self.assertIn("-    user_id,", diff_text)
        self.assertIn("+    customer_id,", diff_text)


if __name__ == "__main__":
    unittest.main()
