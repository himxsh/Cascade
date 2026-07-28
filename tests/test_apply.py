"""Self-checks for Phase 3 Act + write-back (dry-run, no live secrets)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.apply import remediations_to_files, run_apply
from cascade.comment import build_pr_comment
from cascade.datahub_write import (
    TAG_BREAKING_PENDING,
    TAG_MIGRATED,
    TAG_RETRAIN,
    mark_migrated,
    write_dataset_breaking,
    write_ml_retrain,
)
from cascade.github_act import open_or_update_downstream_pr, post_pr_comment, write_comment_artifact

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_REPORT = ROOT / "tests" / "golden" / "raw_orders_rename" / "expected_impact_report.json"
GOLDEN_SQL = ROOT / "tests" / "golden" / "raw_orders_rename" / "expected_fct_orders.sql"


class TestComment(unittest.TestCase):
    def test_includes_blast_radius_and_rationale(self):
        report = json.loads(GOLDEN_REPORT.read_text())
        report["remediations"][1]["rewritten_sql"] = GOLDEN_SQL.read_text()
        md = build_pr_comment(report)
        self.assertIn("Cascade impact report", md)
        self.assertIn("Blast radius", md)
        self.assertIn("analytics.fct_orders", md)
        self.assertIn("Agent remediations", md)
        self.assertIn("rewrite", md)
        self.assertIn("rewriting to customer_id", md)
        self.assertIn("retrain-suggested", md)


class TestGitHubAct(unittest.TestCase):
    def test_dry_run_writes_comment_without_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
            with mock.patch.dict(os.environ, env, clear=True):
                result = post_pr_comment("hello", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            self.assertFalse(result["posted"])
            self.assertEqual(Path(tmp, "pr_comment.md").read_text(), "hello")

    def test_downstream_dry_run_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
            cwd = os.getcwd()
            os.chdir(ROOT)
            try:
                with mock.patch.dict(os.environ, env, clear=True):
                    result = open_or_update_downstream_pr(
                        {"examples/models/fct_orders.sql": GOLDEN_SQL.read_text()},
                        out_dir=tmp,
                        reviewers=["alice"],
                    )
            finally:
                os.chdir(cwd)
            self.assertTrue(result["dry_run"])
            self.assertTrue(Path(tmp, "rewritten", "fct_orders.sql").exists())
            self.assertTrue(Path(tmp, "downstream_pr.json").exists())
            patch = Path(tmp, "downstream_pr.diff").read_text()
            self.assertIn("-    user_id,", patch)
            self.assertIn("+    customer_id,", patch)
            body = Path(tmp, "downstream_pr.md").read_text()
            self.assertIn("@alice", body)

    def test_owner_urns_to_reviewers(self):
        from cascade.github_act import owner_urns_to_reviewers
        self.assertEqual(
            owner_urns_to_reviewers(["urn:li:corpuser:alice", "urn:li:corpuser:bob"]),
            ["alice", "bob"],
        )


class TestDataHubWrite(unittest.TestCase):
    def test_dataset_writeback_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CASCADE_WRITEBACK": ""}, clear=False):
                os.environ.pop("CASCADE_WRITEBACK", None)
                result = write_dataset_breaking("urn:li:dataset:x", plan_doc="plan", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "datahub_writeback.json").read_text())
            tags = [a for a in saved["actions"] if a["op"] == "add_tags"][0]["tags"]
            self.assertIn(TAG_BREAKING_PENDING, tags)

    def test_ml_writeback_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("CASCADE_WRITEBACK", None)
            result = write_ml_retrain("urn:li:mlModel:x", via_feature="user_id", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "ml_writeback.json").read_text())
            tags = [a for a in saved["actions"] if a["op"] == "add_tags"][0]["tags"]
            self.assertIn(TAG_RETRAIN, tags)

    def test_migrated_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("CASCADE_WRITEBACK", None)
            result = mark_migrated("urn:li:dataset:x", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "migrated.json").read_text())
            ops = {a["op"]: a for a in saved["actions"]}
            self.assertIn(TAG_BREAKING_PENDING, ops["remove_tags"]["tags"])
            self.assertIn(TAG_MIGRATED, ops["add_tags"]["tags"])

    def test_live_flag_calls_http(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CASCADE_WRITEBACK": "1", "DATAHUB_GMS_URL": "http://gms"}):
                with mock.patch("cascade.datahub_write._post_json", return_value={"ok": True}) as post:
                    result = write_dataset_breaking("urn:li:dataset:x", plan_doc="plan", out_dir=tmp)
            self.assertFalse(result["dry_run"])
            self.assertTrue(result.get("applied"))
            self.assertGreaterEqual(post.call_count, 1)


class TestApply(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_run_apply_dry_run_end_to_end(self):
        report = json.loads(GOLDEN_REPORT.read_text())
        report["remediations"][1]["rewritten_sql"] = GOLDEN_SQL.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "CASCADE_WRITEBACK")}
            with mock.patch.dict(os.environ, env, clear=True):
                summary = run_apply(report, out_dir=tmp, mark_lifecycle=True)
            self.assertTrue(Path(tmp, "pr_comment.md").exists())
            self.assertTrue(Path(tmp, "rewritten", "fct_orders.sql").exists())
            self.assertTrue(Path(tmp, "downstream_pr.diff").exists())
            self.assertTrue(Path(tmp, "downstream_pr.md").exists())
            self.assertTrue(Path(tmp, "datahub_writeback.json").exists())
            self.assertTrue(Path(tmp, "ml_writeback.json").exists())
            self.assertTrue(Path(tmp, "migrated.json").exists())
            self.assertTrue(Path(tmp, "apply_summary.json").exists())
            self.assertTrue(summary["comment"]["dry_run"])
            self.assertIn("alice", summary["downstream_pr"]["reviewers"])
            sql = Path(tmp, "rewritten", "fct_orders.sql").read_text()
            self.assertEqual(sql, GOLDEN_SQL.read_text())
            patch = Path(tmp, "downstream_pr.diff").read_text()
            self.assertIn("-    user_id,", patch)
            self.assertIn("+    customer_id,", patch)

    def test_remediations_to_files(self):
        files = remediations_to_files([
            {"path": "a.sql", "rewritten_sql": "SELECT 1", "strategy": "rewrite"},
            {"strategy": "adapter_view"},
        ])
        self.assertEqual(files, {"a.sql": "SELECT 1"})


class TestWriteCommentArtifact(unittest.TestCase):
    def test_write_comment_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_comment_artifact(tmp, "# hi")
            self.assertEqual(path.read_text(), "# hi")


if __name__ == "__main__":
    unittest.main()
