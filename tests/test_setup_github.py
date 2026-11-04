import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.setup_cmd import _doctor_github, _try_set_gh_secrets, run_setup


class TestGitHubSetup(unittest.TestCase):
    def setup_live(self, td, env, prompt=None, non_interactive=False, skip_secrets=False):
        root = Path(td.name if isinstance(td, tempfile.TemporaryDirectory) else td)
        (root / "models").mkdir()
        (root / "models" / "x.sql").write_text("select 1")
        calls = []
        def run(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0)
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("cascade.setup_cmd._resolve_git_root", return_value=root), \
             mock.patch("cascade.setup_cmd.health_check", return_value=True), \
             mock.patch("cascade.setup_cmd.search_dataset_hits", return_value=([], False)), \
             mock.patch("cascade.setup_cmd.run_doctor", return_value=([], 0)), \
             mock.patch("cascade.setup_cmd.shutil.which", return_value="gh"), \
             mock.patch("cascade.setup_cmd.subprocess.run", side_effect=run):
            lines, _ = run_setup(root, prompt=prompt, non_interactive=non_interactive, skip_secrets=skip_secrets)
        return lines, calls

    def test_interactive_setup_prompts_key_and_model(self):
        answers = iter(["https://gms.invalid", "TOP-SECRET", "model-x"])
        lines, calls = self.setup_live(tempfile.TemporaryDirectory(), {}, lambda _: next(answers))
        self.assertNotIn("TOP-SECRET", "\n".join(lines))
        self.assertIn(("gh secret set LLM_API_KEY", "TOP-SECRET"), [(" ".join(a), k.get("input")) for a,k in calls])
        self.assertIn(("gh variable set CASCADE_MODE", "llm"), [(" ".join(a), k.get("input")) for a,k in calls])
        self.assertIn(("gh variable set LLM_MODEL", "model-x"), [(" ".join(a), k.get("input")) for a,k in calls])

    def test_empty_interactive_key_does_not_enable_llm(self):
        answers = iter(["https://gms.invalid", "", "model-x"])
        lines, calls = self.setup_live(tempfile.TemporaryDirectory(), {}, lambda _: next(answers))
        self.assertFalse(any(a == ["gh", "secret", "set", "LLM_API_KEY"] for a,_ in calls))
        self.assertFalse(any(a == ["gh", "variable", "set", "CASCADE_MODE"] for a,_ in calls))
        self.assertIn("hint add LLM_API_KEY, then run: gh variable set CASCADE_MODE --body llm", lines)

    def test_noninteractive_missing_and_present_env(self):
        lines, calls = self.setup_live(tempfile.TemporaryDirectory(), {"DATAHUB_GMS_URL":"https://gms.invalid"}, lambda _: self.fail("prompt called"), True)
        self.assertFalse(any(a == ["gh", "secret", "set", "LLM_API_KEY"] for a,_ in calls))
        self.assertFalse(any(a[:2] == ["gh", "variable"] for a,_ in calls))
        self.assertTrue(any("hint add LLM_API_KEY" in line for line in lines))
        _, calls = self.setup_live(tempfile.TemporaryDirectory(), {"DATAHUB_GMS_URL":"https://gms.invalid", "LLM_API_KEY":"key", "LLM_MODEL":"model"}, lambda _: self.fail("prompt called"), True)
        self.assertTrue(any(a == ["gh", "secret", "set", "LLM_API_KEY"] and k["input"] == "key" for a,k in calls))
        self.assertTrue(any(a == ["gh", "variable", "set", "LLM_MODEL"] and k["input"] == "model" for a,k in calls))

    def test_missing_or_unauthenticated_gh_returns_instructions(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch("cascade.setup_cmd.shutil.which", return_value=None), mock.patch("cascade.setup_cmd.subprocess.run") as run:
                lines = _try_set_gh_secrets(Path(td), "url", None, "key", {"CASCADE_MODE":"llm", "LLM_MODEL":"m"})
                run.assert_not_called()
            self.assertTrue(any("gh secret set" in line for line in lines))
            self.assertTrue(any("gh variable set" in line for line in lines))
            with mock.patch("cascade.setup_cmd.shutil.which", return_value="gh"), mock.patch("cascade.setup_cmd.subprocess.run", return_value=subprocess.CompletedProcess([], 1)):
                lines = _try_set_gh_secrets(Path(td), "url", None, "key", {"CASCADE_MODE":"llm"})
            self.assertTrue(any("gh secret set" in line for line in lines))
            self.assertTrue(any("gh variable set" in line for line in lines))

    def test_skip_secrets_makes_no_gh_calls(self):
        _, calls = self.setup_live(tempfile.TemporaryDirectory(), {"DATAHUB_GMS_URL":"https://gms.invalid"}, non_interactive=True, skip_secrets=True)
        self.assertEqual(calls, [])

    def test_values_are_stdin_and_key_never_printed(self):
        with tempfile.TemporaryDirectory() as td:
            calls = []
            def run(args, **kwargs):
                calls.append((args, kwargs))
                return subprocess.CompletedProcess(args, 0)
            with mock.patch("cascade.setup_cmd.shutil.which", return_value="gh"), mock.patch(
                "cascade.setup_cmd.subprocess.run", side_effect=run
            ):
                lines = _try_set_gh_secrets(Path(td), "url", None, "TOP-SECRET", {"CASCADE_MODE": "llm", "LLM_MODEL": "m"})
            self.assertNotIn("TOP-SECRET", "\n".join(lines))
            secret_call = next(c for c in calls if c[0] == ["gh", "secret", "set", "LLM_API_KEY"])
            self.assertEqual(secret_call[1]["input"], "TOP-SECRET")
            variable_calls = [c for c in calls if c[0][:3] == ["gh", "variable", "set"]]
            self.assertEqual([(c[0][-1], c[1]["input"]) for c in variable_calls], [("CASCADE_MODE", "llm"), ("LLM_MODEL", "m")])

    def test_doctor_reports_missing_items_and_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            responses = [
                subprocess.CompletedProcess([], 0),
                subprocess.CompletedProcess([], 0, "LLM_API_KEY\t2026\n", ""),
                subprocess.CompletedProcess([], 0, "CASCADE_MODE\tllm\n", ""),
            ]
            with mock.patch("cascade.setup_cmd._resolve_git_root", return_value=root), mock.patch(
                "cascade.setup_cmd.shutil.which", return_value="gh"
            ), mock.patch("cascade.setup_cmd.subprocess.run", side_effect=responses):
                lines = []
                _doctor_github(root, lines)
            self.assertIn("ok   GitHub secret LLM_API_KEY", lines)
            self.assertIn("warn GitHub secret DATAHUB_GMS_URL missing — gh secret set DATAHUB_GMS_URL", lines)
            self.assertIn("ok   GitHub variable CASCADE_MODE", lines)
            self.assertIn("warn GitHub variable LLM_MODEL missing — gh variable set LLM_MODEL", lines)
            self.assertTrue(any("cascade.yml missing" in line for line in lines))

    def test_doctor_absent_or_failure_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for which, run in (
                (None, None),
                ("gh", subprocess.CompletedProcess([], 1)),
            ):
                with mock.patch("cascade.setup_cmd._resolve_git_root", return_value=root), mock.patch(
                    "cascade.setup_cmd.shutil.which", return_value=which
                ), mock.patch("cascade.setup_cmd.subprocess.run", return_value=run):
                    lines = []
                    _doctor_github(root, lines)
                    self.assertEqual(lines, [])
