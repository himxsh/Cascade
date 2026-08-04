"""Self-check: UI pipeline returns a real ImpactReport from the demo fixture (offline)."""

from __future__ import annotations

import unittest
from pathlib import Path

from cascade.demo import DEFAULT_DIFF, DEFAULT_URN
from cascade.ui_run import load_demo_diff, run_ui_pipeline

ROOT = Path(__file__).resolve().parents[1]


class TestUiRun(unittest.TestCase):
    def test_demo_diff_path_exists(self) -> None:
        demo = load_demo_diff()
        self.assertEqual(demo["urn"], DEFAULT_URN)
        self.assertTrue(Path(DEFAULT_DIFF).is_file())
        self.assertIn("FIELD_RENAMED", demo["diff"])

    def test_fixture_pipeline_impact_report_shape(self) -> None:
        demo = load_demo_diff()
        payload = run_ui_pipeline(
            diff_text=demo["diff"],
            urn=demo["urn"],
            source="fixture",
            models_dir=ROOT / "examples" / "models",
        )

        report = payload["report"]
        self.assertEqual(report["source_urn"], DEFAULT_URN)
        self.assertEqual(report["severity"], "high")
        self.assertEqual(len(report["changes"]), 1)
        self.assertEqual(report["changes"][0]["type"], "FIELD_RENAMED")
        self.assertEqual(len(report["downstream"]), 3)
        self.assertTrue(report["ml_impact"])
        self.assertTrue(report["remediations"])
        self.assertIn("strategy", report["remediations"][0])
        self.assertIn("rationale", report["remediations"][0])

        self.assertTrue(payload["graph"]["nodes"])
        self.assertTrue(payload["graph"]["edges"])
        self.assertTrue(payload["files"])
        f = payload["files"][0]
        self.assertIn("user_id", f["before"])
        self.assertIn("customer_id", f["after"])
        self.assertIn("datahub_writeback.json", payload["apply"])
        self.assertIn("ml_writeback.json", payload["apply"])


if __name__ == "__main__":
    unittest.main()
