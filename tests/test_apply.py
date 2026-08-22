"""Self-checks for Phase 3 Act + write-back (dry-run, no live secrets)."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from cascade.apply import remediations_to_files, run_apply
from cascade.comment import (
    STACK_COMMENT_MARKER,
    blast_mermaid,
    build_pr_comment,
    build_remediation_pr_body,
    build_stack_comment,
)
from cascade.datahub_write import (
    TAG_BREAKING_PENDING,
    TAG_MIGRATED,
    TAG_RETRAIN,
    aspect_plan_dataset_breaking,
    aspect_plan_migrated,
    aspect_plan_ml_retrain,
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
        self.assertIn("fct_orders", md)
        self.assertIn("```mermaid", md)
        self.assertIn("user_id to customer_id", md)
        self.assertIn("retrain suggested", md)
        self.assertIn("/cascade stack", md)
        self.assertNotIn("**Stacked PR:**", md)
        stacked = build_stack_comment("https://github.com/o/r/pull/9")
        self.assertIn("## Cascade stacked PR", stacked)
        self.assertIn("**Stacked PR:** https://github.com/o/r/pull/9", stacked)
        self.assertNotIn("Cascade impact report", stacked)

    def test_clear_comment_when_no_downstream(self):
        md = build_pr_comment({
            "source_urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)",
            "changes": [{"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id"}],
            "downstream": [],
            "severity": "medium",
        })
        self.assertIn("No changes needed", md)
        self.assertNotIn("/cascade stack", md)
        self.assertNotIn("```mermaid", md)

    def test_remediation_pr_has_mermaid_not_diff(self):
        report = json.loads(GOLDEN_REPORT.read_text())
        report["remediations"][1]["rewritten_sql"] = GOLDEN_SQL.read_text()
        report["remediations"][1]["agent"] = "deterministic"
        md = build_remediation_pr_body(report)
        self.assertIn("```mermaid", md)
        self.assertIn("What could break", md)
        self.assertIn("How Cascade fixed it", md)
        self.assertIn("fct_orders", md)
        self.assertIn("deterministic", md)
        self.assertNotIn("```diff", md)
        self.assertIn("**Source:**", md)

    def test_blast_mermaid_unique_ids_for_same_short_name(self):
        graph = blast_mermaid({
            "source_urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,shop.public.raw_orders,PROD)",
            "changes": [{"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id"}],
            "downstream": [
                {"urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,shop.public.stg_orders,PROD)"},
                {"urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,other.public.stg_orders,PROD)"},
            ],
        })
        self.assertIsNotNone(graph)
        self.assertIn("s_raw_orders", graph)
        self.assertIn("d0_stg_orders", graph)
        self.assertIn("d1_stg_orders", graph)

    def test_blast_mermaid_overflow_id_distinct_from_source(self):
        downstream = [
            {"urn": f"urn:li:dataset:(urn:li:dataPlatform:postgres,shop.public.n{i},PROD)"}
            for i in range(16)
        ]
        graph = blast_mermaid({
            "source_urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,shop.public.more,PROD)",
            "changes": [{"type": "FIELD_REMOVED", "from": "x"}],
            "downstream": downstream,
        })
        self.assertIsNotNone(graph)
        self.assertIn("s_more", graph)
        self.assertIn("xtra[", graph)
        self.assertNotRegex(graph, r"(?m)^  more\[")


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
            self.assertNotIn("@alice", body)
            self.assertNotIn("Suggested reviewers", body)

    def test_owner_urns_to_reviewers(self):
        from cascade.github_act import owner_urns_to_reviewers
        self.assertEqual(
            owner_urns_to_reviewers(["urn:li:corpuser:alice", "urn:li:corpuser:bob"]),
            ["alice", "bob"],
        )

    def test_remediation_branch_name(self):
        from cascade.github_act import remediation_branch_name
        self.assertEqual(remediation_branch_name(42), "cascade/remediation/42")
        self.assertEqual(remediation_branch_name(None), "cascade/remediation/manual")

    def test_extract_source_urn(self):
        from cascade.github_act import extract_source_urn_from_pr_body
        body = "## Cascade\n\n**Source:** `urn:li:dataset:x`\n"
        self.assertEqual(extract_source_urn_from_pr_body(body), "urn:li:dataset:x")
        marked = "hello\n<!-- cascade:source_urn=urn:li:dataset:y -->\n"
        self.assertEqual(extract_source_urn_from_pr_body(marked), "urn:li:dataset:y")

    def test_git_data_api_open_mocked(self):
        from cascade.github_act import open_or_update_downstream_pr

        calls: list[tuple[str, str]] = []

        posted: dict[str, Any] = {}

        def fake_api(method: str, path: str, body=None):
            calls.append((method, path))
            if method == "GET" and path == "/pulls/7":
                return {
                    "head": {"ref": "feat/rename", "sha": "abc123headsha"},
                    "base": {"ref": "main"},
                }
            if method == "GET" and path.startswith("/git/ref/heads/"):
                if "cascade" in path:
                    raise RuntimeError("GitHub API GET failed: 404 not found")
                return {"object": {"sha": "baseSha"}}
            if method == "GET" and path.startswith("/git/commits/"):
                return {"tree": {"sha": "treeSha"}}
            if method == "POST" and path == "/git/blobs":
                return {"sha": "blobSha"}
            if method == "POST" and path == "/git/trees":
                return {"sha": "newTree"}
            if method == "POST" and path == "/git/commits":
                return {"sha": "commitSha"}
            if method == "POST" and path == "/git/refs":
                return {"ref": "refs/heads/cascade/remediation/7"}
            if method == "GET" and path.startswith("/pulls?"):
                return []  # type: ignore[return-value]
            if method == "POST" and path == "/pulls":
                posted["pull"] = body
                return {"html_url": "https://github.com/o/r/pull/99", "number": 99}
            if method == "POST" and "requested_reviewers" in path:
                return {"requested": True}
            raise AssertionError(f"unexpected {method} {path}")

        def fake_list(method: str, path: str, body=None):
            calls.append((method, path))
            return []

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **os.environ,
                "GITHUB_TOKEN": "t",
                "GITHUB_REPOSITORY": "o/r",
                "CASCADE_OPEN_DOWNSTREAM_PR": "1",
            }
            env.pop("CASCADE_DOWNSTREAM_HEAD", None)
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch("cascade.github_act._github_api", side_effect=fake_api):
                    with mock.patch("cascade.github_act._github_api_list", side_effect=fake_list):
                        result = open_or_update_downstream_pr(
                            {"examples/models/fct_orders.sql": "SELECT 1\n"},
                            out_dir=tmp,
                            reviewers=["alice"],
                            upstream_pr=7,
                            source_urn="urn:li:dataset:x",
                        )
            body = Path(tmp, "downstream_pr.md").read_text()
            self.assertFalse(result["dry_run"])
            self.assertTrue(result["opened"])
            self.assertEqual(result["url"], "https://github.com/o/r/pull/99")
            self.assertEqual(result["mode"], "git_data_api")
            self.assertEqual(result["branch"], "cascade/remediation/7")
            self.assertIn("cascade:source_urn=urn:li:dataset:x", body)
            self.assertTrue(any(m == "POST" and p == "/pulls" for m, p in calls))
            self.assertTrue(any(m == "GET" and p == "/pulls/7" for m, p in calls))
            self.assertEqual(posted["pull"]["base"], "main")
            self.assertEqual(posted["pull"]["head"], "cascade/remediation/7")
            self.assertTrue(any(p == "/git/commits/abc123headsha" for _, p in calls))


class TestDataHubWrite(unittest.TestCase):
    def test_aspect_plan_shapes(self):
        ds = aspect_plan_dataset_breaking("urn:li:dataset:x", "plan body", "desc")
        names = [a["aspectName"] for a in ds]
        self.assertEqual(
            names,
            ["tagProperties", "globalTags", "editableDatasetProperties", "institutionalMemory"],
        )
        self.assertNotIn("cascadeStub", json.dumps(ds))
        ml = aspect_plan_ml_retrain("urn:li:mlModel:x", "body")
        self.assertIn("globalTags", [a["aspectName"] for a in ml])
        mig = aspect_plan_migrated("urn:li:dataset:x", "migrated desc")
        tags = [a for a in mig if a["aspectName"] == "globalTags"][0]
        self.assertIn(f"urn:li:tag:{TAG_MIGRATED}", tags["tags"])
        self.assertIn(f"urn:li:tag:{TAG_BREAKING_PENDING}", tags["removed"])
        desc = [a for a in mig if a["aspectName"] == "editableDatasetProperties"][0]
        self.assertIn("migrated", desc["description"].lower())

    def test_dataset_writeback_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CASCADE_WRITEBACK": ""}, clear=False):
                os.environ.pop("CASCADE_WRITEBACK", None)
                result = write_dataset_breaking("urn:li:dataset:x", plan_doc="plan", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "datahub_writeback.json").read_text())
            tags = [a for a in saved["actions"] if a["op"] == "add_tags"][0]["tags"]
            self.assertIn(TAG_BREAKING_PENDING, tags)
            aspect_names = [a["aspectName"] for a in saved["aspects"]]
            self.assertIn("globalTags", aspect_names)
            self.assertIn("editableDatasetProperties", aspect_names)
            self.assertNotIn("cascadeStub", json.dumps(saved))

    def test_ml_writeback_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("CASCADE_WRITEBACK", None)
            result = write_ml_retrain("urn:li:mlModel:x", via_feature="user_id", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "ml_writeback.json").read_text())
            tags = [a for a in saved["actions"] if a["op"] == "add_tags"][0]["tags"]
            self.assertIn(TAG_RETRAIN, tags)
            self.assertNotIn("cascadeStub", json.dumps(saved))

    def test_migrated_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("CASCADE_WRITEBACK", None)
            result = mark_migrated("urn:li:dataset:x", out_dir=tmp)
            self.assertTrue(result["dry_run"])
            saved = json.loads(Path(tmp, "migrated.json").read_text())
            ops = {a["op"]: a for a in saved["actions"]}
            self.assertIn(TAG_BREAKING_PENDING, ops["remove_tags"]["tags"])
            self.assertIn(TAG_MIGRATED, ops["add_tags"]["tags"])
            self.assertIn("migrated", ops["update_description"]["description"].lower())
            self.assertNotIn("pending remediation", ops["update_description"]["description"].lower())
            aspect_names = [a["aspectName"] for a in saved["aspects"]]
            self.assertIn("editableDatasetProperties", aspect_names)

    def test_live_flag_calls_emit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"CASCADE_WRITEBACK": "1", "DATAHUB_GMS_URL": "http://gms"}):
                with mock.patch("cascade.datahub_write._emit_plan") as emit:
                    result = write_dataset_breaking("urn:li:dataset:x", plan_doc="plan", out_dir=tmp)
            self.assertFalse(result["dry_run"])
            self.assertTrue(result.get("applied"))
            emit.assert_called_once()
            plan = emit.call_args[0][0]
            self.assertEqual(plan[0]["aspectName"], "tagProperties")
            self.assertNotIn("cascadeStub", json.dumps(plan))


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
            env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_TOKEN", "CASCADE_WRITEBACK", "CASCADE_OPEN_DOWNSTREAM_PR")}
            with mock.patch.dict(os.environ, env, clear=True):
                summary = run_apply(report, out_dir=tmp, mark_lifecycle=True, audit_root=tmp)
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
            self.assertIn("policy", summary)
            sql = Path(tmp, "rewritten", "fct_orders.sql").read_text()
            self.assertEqual(sql, GOLDEN_SQL.read_text())
            patch = Path(tmp, "downstream_pr.diff").read_text()
            self.assertIn("-    user_id,", patch)
            self.assertIn("+    customer_id,", patch)
            body = Path(tmp, "downstream_pr.md").read_text()
            self.assertIn("```mermaid", body)
            self.assertNotIn("```diff", body)

    def test_stack_apply_posts_new_comment_not_impact(self):
        report = json.loads(GOLDEN_REPORT.read_text())
        report["remediations"][1]["rewritten_sql"] = GOLDEN_SQL.read_text()
        posted: dict[str, Any] = {}

        def fake_post(body, **kwargs):
            posted["body"] = body
            posted["kwargs"] = kwargs
            return {"posted": True, "updated": False, "dry_run": False}

        with tempfile.TemporaryDirectory() as tmp:
            env = {
                **{k: v for k, v in os.environ.items() if k != "CASCADE_WRITEBACK"},
                "GITHUB_TOKEN": "t",
                "GITHUB_REPOSITORY": "o/r",
                "CASCADE_OPEN_DOWNSTREAM_PR": "1",
                "CASCADE_RUN_ID": "stack-comment-test",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch(
                    "cascade.apply.open_or_update_downstream_pr",
                    return_value={
                        "dry_run": False,
                        "opened": True,
                        "url": "https://github.com/o/r/pull/10",
                    },
                ):
                    with mock.patch("cascade.apply.post_pr_comment", side_effect=fake_post):
                        summary = run_apply(
                            report, out_dir=tmp, pr_number=9, mode="apply", audit_root=tmp
                        )
        self.assertIn("## Cascade stacked PR", posted["body"])
        self.assertIn("**Stacked PR:** https://github.com/o/r/pull/10", posted["body"])
        self.assertNotIn("Cascade impact report", posted["body"])
        self.assertEqual(posted["kwargs"]["marker"], STACK_COMMENT_MARKER)
        self.assertTrue(summary["policy"]["ok"])

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
