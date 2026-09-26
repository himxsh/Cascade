"""init / setup / doctor / fixture-missing self-checks."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.cli import main
from cascade.config import load_config, resolve_rewrite_mode
from cascade.datahub_fixture import load_catalog
from cascade.pip_notice import NOTICE, emit_install_notice
from cascade.setup_cmd import run_doctor, run_init, run_setup

ROOT = Path(__file__).resolve().parents[1]
STG_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)"
RAW_URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)"


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)


def _write_sql(root: Path, rel: str = "models/stg_orders.sql") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("select 1\n")
    return path


class TestInit(unittest.TestCase):
    def test_writes_config_env_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            notes = run_init(root)
            self.assertTrue((root / ".cascade" / "config.json").is_file())
            self.assertTrue((root / ".env.example").is_file())
            self.assertTrue((root / ".github" / "workflows" / "cascade.yml").is_file())
            self.assertTrue(any(n.startswith("wrote") for n in notes))
            cfg = json.loads((root / ".cascade" / "config.json").read_text())
            self.assertEqual(cfg["rewrite"]["mode"], "deterministic")
            again = run_init(root)
            self.assertTrue(any("skip" in n for n in again))


class TestRewriteMode(unittest.TestCase):
    def test_default_deterministic(self):
        env = {k: v for k, v in os.environ.items() if k != "CASCADE_MODE"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(resolve_rewrite_mode(None), "deterministic")

    def test_cli_beats_env(self):
        with mock.patch.dict(os.environ, {"CASCADE_MODE": "llm"}, clear=False):
            self.assertEqual(resolve_rewrite_mode("deterministic"), "deterministic")

    def test_explicit_config_path_used_for_rewrite_mode(self):
        env = {k: v for k, v in os.environ.items() if k != "CASCADE_MODE"}
        with tempfile.TemporaryDirectory() as td:
            cwd_cfg = Path(td) / ".cascade"
            cwd_cfg.mkdir()
            (cwd_cfg / "config.json").write_text(json.dumps({"rewrite": {"mode": "deterministic"}}))
            other = Path(td) / "other.json"
            other.write_text(json.dumps({"rewrite": {"mode": "llm", "provider": "openai", "model": "gpt-4o"}}))
            loaded = load_config(other)
            with mock.patch.dict(os.environ, env, clear=True):
                old = Path.cwd()
                os.chdir(td)
                try:
                    self.assertEqual(resolve_rewrite_mode(None), "deterministic")
                    self.assertEqual(resolve_rewrite_mode(None, config=loaded), "llm")
                finally:
                    os.chdir(old)

    def test_load_rewrite_block(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "c.json"
            path.write_text(json.dumps({"rewrite": {"mode": "llm", "provider": "openai", "model": "gpt-4o"}}))
            cfg = load_config(path)
        self.assertEqual(cfg.rewrite_mode, "llm")
        self.assertEqual(cfg.rewrite_provider, "openai")
        self.assertEqual(cfg.rewrite_model, "gpt-4o")


class TestFixtureMissing(unittest.TestCase):
    def test_raises_when_no_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            env = {k: v for k, v in os.environ.items() if k != "CASCADE_FIXTURE_PATH"}
            with mock.patch.dict(os.environ, env, clear=True):
                with mock.patch("cascade.datahub_fixture.Path.cwd", return_value=Path(td)):
                    with self.assertRaises(FileNotFoundError):
                        load_catalog("/no/such/fixture.json")


class TestDoctor(unittest.TestCase):
    def test_reports_missing_config(self):
        with tempfile.TemporaryDirectory() as td:
            lines, rc = run_doctor(Path(td))
        self.assertEqual(rc, 1)
        self.assertTrue(any("config missing" in ln for ln in lines))
        self.assertTrue(any("cascade setup" in ln for ln in lines))


class TestSetup(unittest.TestCase):
    def test_rejects_non_git_dir(self):
        with tempfile.TemporaryDirectory() as td:
            lines, rc = run_setup(Path(td), demo=True, non_interactive=True)
        self.assertEqual(rc, 1)
        self.assertTrue(any("not a git repository" in ln for ln in lines))

    def test_non_interactive_no_sql_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            lines, rc = run_setup(root, demo=True, non_interactive=True)
        self.assertEqual(rc, 1)
        self.assertTrue(any("no SQL/dbt files" in ln for ln in lines))
        self.assertFalse((root / ".cascade" / "config.json").is_file())

    def test_demo_writes_scaffolding_offline(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            with mock.patch.dict(os.environ, {"DATAHUB_GMS_URL": "", "DATAHUB_TOKEN": "", "CASCADE_MODE": ""}, clear=False):
                with mock.patch("cascade.setup_cmd.health_check") as health:
                    lines, rc = run_setup(root, demo=True, non_interactive=True)
            health.assert_not_called()
            self.assertEqual(rc, 0, msg=lines)
            self.assertTrue((root / ".cascade" / "config.json").is_file())
            self.assertTrue((root / ".env.example").is_file())
            self.assertTrue((root / ".github" / "workflows" / "cascade.yml").is_file())
            cfg = json.loads((root / ".cascade" / "config.json").read_text())
            self.assertNotIn("YOUR_TABLE", json.dumps(cfg))
            self.assertEqual(cfg["default_urn"], STG_URN)
            self.assertTrue(any(m.get("urn") == STG_URN for m in cfg["mappings"]))
            joined = "\n".join(lines)
            self.assertIn("matched models/stg_orders.sql", joined)
            self.assertIn("Commit these files", joined)
            self.assertIn("/cascade stack", joined)
            self.assertIn("skipped live DataHub", joined)

    def test_non_interactive_missing_env_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            env = {
                k: v
                for k, v in os.environ.items()
                if k not in ("DATAHUB_GMS_URL", "DATAHUB_TOKEN")
            }
            with mock.patch.dict(os.environ, env, clear=True):
                lines, rc = run_setup(root, non_interactive=True, skip_secrets=True)
        self.assertEqual(rc, 1)
        self.assertTrue(any("DATAHUB_GMS_URL is unset" in ln for ln in lines))
        self.assertFalse(any("http://" in ln or "https://" in ln for ln in lines))

    def test_live_unreachable_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            with mock.patch.dict(
                os.environ,
                {
                    "DATAHUB_GMS_URL": "https://gms.example.invalid",
                    "DATAHUB_TOKEN": "secret-token",
                    "CASCADE_MODE": "",
                },
                clear=False,
            ):
                with mock.patch("cascade.setup_cmd.health_check", return_value=False):
                    lines, rc = run_setup(root, non_interactive=True, skip_secrets=True)
        self.assertEqual(rc, 1)
        self.assertTrue(any("DataHub unreachable" in ln for ln in lines))
        self.assertFalse(any("secret-token" in ln for ln in lines))

    def test_live_unique_match_writes_urn(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            with mock.patch.dict(
                os.environ,
                {
                    "DATAHUB_GMS_URL": "https://gms.example.invalid",
                    "DATAHUB_TOKEN": "secret-token",
                    "CASCADE_MODE": "",
                },
                clear=False,
            ):
                with mock.patch("cascade.setup_cmd.health_check", return_value=True):
                    with mock.patch(
                        "cascade.setup_cmd.search_dataset_urns",
                        return_value=[STG_URN],
                    ):
                        lines, rc = run_setup(root, non_interactive=True, skip_secrets=True)
            self.assertEqual(rc, 0, msg=lines)
            cfg = json.loads((root / ".cascade" / "config.json").read_text())
            self.assertEqual(cfg["default_urn"], STG_URN)
            self.assertTrue(any(m.get("path") == "models/stg_orders.sql" for m in cfg["mappings"]))
            joined = "\n".join(lines)
            self.assertIn("matched models/stg_orders.sql", joined)
            self.assertNotIn("secret-token", joined)

    def test_gh_missing_prints_copy_paste_block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            with mock.patch.dict(
                os.environ,
                {
                    "DATAHUB_GMS_URL": "https://gms.example.invalid",
                    "DATAHUB_TOKEN": "secret-token",
                    "CASCADE_MODE": "",
                },
                clear=False,
            ):
                with mock.patch("cascade.setup_cmd.health_check", return_value=True):
                    with mock.patch("cascade.setup_cmd.search_dataset_urns", return_value=[STG_URN]):
                        with mock.patch("cascade.setup_cmd.shutil.which", return_value=None):
                            lines, rc = run_setup(root, non_interactive=True, skip_secrets=False)
            self.assertEqual(rc, 0, msg=lines)
            joined = "\n".join(lines)
            self.assertIn("gh secret set DATAHUB_GMS_URL", joined)
            self.assertNotIn("secret-token", joined)

    def test_interactive_continue_without_sql(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            with mock.patch.dict(os.environ, {"DATAHUB_GMS_URL": "", "DATAHUB_TOKEN": "", "CASCADE_MODE": ""}, clear=False):
                lines, rc = run_setup(
                    root,
                    demo=True,
                    prompt=lambda _msg: "y",
                )
            self.assertEqual(rc, 0, msg=lines)
            self.assertTrue((root / ".cascade" / "config.json").is_file())
            cfg = json.loads((root / ".cascade" / "config.json").read_text())
            self.assertEqual(cfg["default_urn"], RAW_URN)

    def test_live_ambiguous_leaves_skeleton(self):
        other = "urn:li:dataset:(urn:li:dataPlatform:postgres,shop.stg_orders,PROD)"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            with mock.patch.dict(
                os.environ,
                {
                    "DATAHUB_GMS_URL": "https://gms.example.invalid",
                    "DATAHUB_TOKEN": "",
                    "CASCADE_MODE": "",
                },
                clear=False,
            ):
                with mock.patch("cascade.setup_cmd.health_check", return_value=True):
                    with mock.patch(
                        "cascade.setup_cmd.search_dataset_urns",
                        return_value=[STG_URN, other],
                    ):
                        lines, rc = run_setup(root, non_interactive=True, skip_secrets=True)
            self.assertEqual(rc, 0, msg=lines)
            cfg = json.loads((root / ".cascade" / "config.json").read_text())
            self.assertIn("YOUR_TABLE", json.dumps(cfg))
            joined = "\n".join(lines)
            self.assertIn("ambiguous models/stg_orders.sql", joined)
            self.assertIn("TODO:", joined)


class TestSetupCli(unittest.TestCase):
    def test_setup_help_lists_flags(self):
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["cascade", "setup", "--help"]):
            with mock.patch.object(sys, "stdout", buf):
                with self.assertRaises(SystemExit) as cm:
                    main()
        self.assertEqual(cm.exception.code, 0)
        text = buf.getvalue()
        self.assertIn("--demo", text)
        self.assertIn("--non-interactive", text)
        self.assertIn("--skip-secrets", text)

    def test_setup_demo_via_main(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _git_init(root)
            _write_sql(root)
            buf = io.StringIO()
            argv = [
                "cascade",
                "setup",
                "--demo",
                "--non-interactive",
                "--dir",
                str(root),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(sys, "stdout", buf):
                with mock.patch.dict(
                    os.environ,
                    {"DATAHUB_GMS_URL": "", "DATAHUB_TOKEN": "", "CASCADE_MODE": ""},
                    clear=False,
                ):
                    main()
            self.assertTrue((root / ".cascade" / "config.json").is_file())
            self.assertIn("Commit these files", buf.getvalue())


class TestPipNotice(unittest.TestCase):
    def test_notice_text(self):
        self.assertIn("cascade setup", NOTICE)
        self.assertIn("DataHub", NOTICE)
        self.assertIn("--demo", NOTICE)
        self.assertLessEqual(NOTICE.count("\n"), 4)

    def test_pyproject_uses_in_tree_backend(self):
        text = (ROOT / "pyproject.toml").read_text()
        self.assertIn('build-backend = "cascade.build_meta"', text)
        self.assertIn("backend-path", text)

    def test_emit_writes_stderr_not_stdout(self):
        err = io.StringIO()
        out = io.StringIO()
        with mock.patch.object(sys, "stderr", err), mock.patch.object(sys, "stdout", out):
            with mock.patch("builtins.open", side_effect=OSError("no tty")):
                emit_install_notice()
        self.assertIn("cascade setup", err.getvalue())
        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
