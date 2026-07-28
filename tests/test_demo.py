"""Self-check for cascade demo one-command path."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]


class TestDemo(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_run_demo_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("GITHUB_TOKEN", "CASCADE_WRITEBACK", "CASCADE_DOWNSTREAM_HEAD")
            }
            with mock.patch.dict(os.environ, env, clear=True):
                result = run_demo(out_dir=tmp)
            self.assertEqual(result["severity"], "high")
            self.assertGreater(result["remediation_count"], 0)
            self.assertTrue(Path(tmp, "generate", "impact_report.json").exists())
            self.assertTrue(Path(tmp, "generate", "fct_orders.sql").exists())
            self.assertTrue(Path(tmp, "apply", "pr_comment.md").exists())
            self.assertTrue(Path(tmp, "apply", "downstream_pr.diff").exists())
            self.assertTrue(Path(tmp, "demo_summary.json").exists())
            sql = Path(tmp, "generate", "fct_orders.sql").read_text()
            self.assertIn("customer_id", sql)
            self.assertNotIn("user_id", sql)


if __name__ == "__main__":
    unittest.main()
