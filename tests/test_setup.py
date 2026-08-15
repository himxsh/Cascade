"""init / doctor / fixture-missing self-checks."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.config import load_config, resolve_rewrite_mode
from cascade.datahub_fixture import load_catalog
from cascade.setup_cmd import run_doctor, run_init


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


if __name__ == "__main__":
    unittest.main()
