"""Tests for path→URN config + changed_paths."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.config import CascadeConfig, load_config, resolve_urn
from cascade.diff_parser import changed_paths


class TestChangedPaths(unittest.TestCase):
    def test_extracts_b_side(self):
        text = """\
diff --git a/models/stg_orders.sql b/models/stg_orders.sql
index a..b 100644
--- a/models/stg_orders.sql
+++ b/models/stg_orders.sql
@@ -1 +1 @@
-x
+y
diff --git a/examples/models/fct_orders.sql b/examples/models/fct_orders.sql
--- a/examples/models/fct_orders.sql
+++ b/examples/models/fct_orders.sql
@@ -1 +1 @@
-a
+b
"""
        self.assertEqual(
            changed_paths(text),
            ["models/stg_orders.sql", "examples/models/fct_orders.sql"],
        )


class TestConfig(unittest.TestCase):
    def test_load_list_mappings_longest_prefix(self):
        raw = {
            "default_urn": "urn:default",
            "models_dir": "examples/models",
            "mappings": [
                {"path": "models/", "urn": "urn:models"},
                {"path": "models/stg_orders.sql", "urn": "urn:stg"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "config.json"
            path.write_text(json.dumps(raw))
            cfg = load_config(path)
        self.assertEqual(cfg.default_urn, "urn:default")
        self.assertEqual(cfg.models_dir, "examples/models")
        self.assertEqual(
            resolve_urn(["models/stg_orders.sql"], cfg),
            "urn:stg",
        )
        self.assertEqual(resolve_urn(["models/other.sql"], cfg), "urn:models")

    def test_dict_mappings_shorthand(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "c.json"
            path.write_text(json.dumps({"mappings": {"examples/": "urn:ex"}}))
            cfg = load_config(path)
        self.assertEqual(resolve_urn(["examples/diffs/x.sql"], cfg), "urn:ex")

    def test_explicit_beats_mapping(self):
        cfg = CascadeConfig(mappings=[("models/", "urn:mapped")], default_urn="urn:def")
        self.assertEqual(
            resolve_urn(["models/a.sql"], cfg, explicit="urn:cli"),
            "urn:cli",
        )

    def test_env_fallback(self):
        cfg = CascadeConfig()
        with mock.patch.dict(os.environ, {"CASCADE_SOURCE_URN": "urn:env"}, clear=False):
            self.assertEqual(resolve_urn([], cfg), "urn:env")

    def test_default_urn(self):
        cfg = CascadeConfig(default_urn="urn:def")
        env = {k: v for k, v in os.environ.items() if k != "CASCADE_SOURCE_URN"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(resolve_urn([], cfg), "urn:def")

    def test_missing_raises(self):
        cfg = CascadeConfig()
        env = {k: v for k, v in os.environ.items() if k != "CASCADE_SOURCE_URN"}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(SystemExit):
                resolve_urn(["unmapped/x.sql"], cfg)

    def test_missing_file_empty(self):
        cfg = load_config("/nonexistent/cascade-config.json")
        self.assertEqual(cfg.mappings, [])
        self.assertIsNone(cfg.default_urn)


if __name__ == "__main__":
    unittest.main()
