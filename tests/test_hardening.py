"""Phase 5 hardening: policy, audit, idempotent comment upsert."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.apply import run_apply
from cascade.audit import make_run_id, write_run_audit
from cascade.github_act import post_pr_comment
from cascade.policy import evaluate_policy

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_REPORT = ROOT / "tests" / "golden" / "raw_orders_rename" / "expected_impact_report.json"
GOLDEN_SQL = ROOT / "tests" / "golden" / "raw_orders_rename" / "expected_fct_orders.sql"


class TestPolicy(unittest.TestCase):
    def test_high_without_stack_request_passes(self):
        result = evaluate_policy({"severity": "high"}, remediation_open=False)
        self.assertTrue(result["ok"])

    def test_high_stack_without_pr_fails(self):
        result = evaluate_policy(
            {"severity": "high"}, remediation_open=False, stack_requested=True
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "high_without_remediation")

    def test_high_with_remediation_passes(self):
        result = evaluate_policy({"severity": "high"}, remediation_open=True)
        self.assertTrue(result["ok"])

    def test_low_passes(self):
        result = evaluate_policy({"severity": "low"}, remediation_open=False)
        self.assertTrue(result["ok"])


class TestAudit(unittest.TestCase):
    def test_write_run_audit_copies_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            apply_out = Path(tmp) / "apply"
            apply_out.mkdir()
            (apply_out / "pr_comment.md").write_text("hi")
            (apply_out / "rewritten").mkdir()
            (apply_out / "rewritten" / "a.sql").write_text("SELECT 1")
            run_dir = write_run_audit(
                run_id="test-run",
                report={"source_urn": "urn:x"},
                summary={"mode": "dry-run"},
                apply_out=apply_out,
                root=tmp,
            )
            self.assertTrue((run_dir / "impact_report.json").is_file())
            self.assertTrue((run_dir / "pr_comment.md").is_file())
            self.assertTrue((run_dir / "rewritten" / "a.sql").is_file())

    def test_make_run_id_from_env(self):
        with mock.patch.dict(os.environ, {"CASCADE_RUN_ID": "fixed-id"}):
            self.assertEqual(make_run_id(pr_number=1), "fixed-id")


class TestIdempotentComment(unittest.TestCase):
    def test_updates_existing_cascade_comment(self):
        calls: list[tuple[str, str]] = []

        def fake_api(method: str, path: str, body=None):
            calls.append((method, path))
            if method == "PATCH":
                return {"id": 9, "html_url": "https://example/c/9"}
            raise AssertionError(path)

        def fake_list(method: str, path: str, body=None):
            return [{
                "id": 9,
                "body": "## Cascade impact report\n\nold",
                "html_url": "https://example/c/9",
            }]

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(
                os.environ,
                {"GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"},
                clear=False,
            ):
                with mock.patch("cascade.github_act._github_api", side_effect=fake_api):
                    with mock.patch("cascade.github_act._github_api_list", side_effect=fake_list):
                        result = post_pr_comment(
                            "## Cascade impact report\n\nnew",
                            pr_number=3,
                            out_dir=tmp,
                        )
        self.assertTrue(result["posted"])
        self.assertTrue(result["updated"])
        self.assertTrue(any(m == "PATCH" for m, _ in calls))


class TestApplyMode(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        os.chdir(ROOT)

    def tearDown(self):
        os.chdir(self._cwd)

    def test_dry_run_mode_forces_dry_even_with_open_flag(self):
        report = json.loads(GOLDEN_REPORT.read_text())
        report["remediations"][1]["rewritten_sql"] = GOLDEN_SQL.read_text()
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **{k: v for k, v in os.environ.items() if k != "CASCADE_WRITEBACK"},
                "GITHUB_TOKEN": "t",
                "GITHUB_REPOSITORY": "o/r",
                "CASCADE_OPEN_DOWNSTREAM_PR": "1",
                "CASCADE_RUN_ID": "mode-test",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                summary = run_apply(
                    report,
                    out_dir=tmp,
                    mode="dry-run",
                    pr_number=1,
                    audit_root=tmp,
                )
            self.assertEqual(summary["mode"], "dry-run")
            self.assertTrue(summary["downstream_pr"]["dry_run"])
            self.assertTrue(summary["comment"]["dry_run"])
            self.assertFalse(summary["policy"]["ok"])  # OPEN set, high, dry-run did not open
            self.assertTrue(Path(tmp, "apply_summary.json").is_file())
            self.assertTrue(Path(tmp, "cascade", "runs", "mode-test", "apply_summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
