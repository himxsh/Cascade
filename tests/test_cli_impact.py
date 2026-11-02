from __future__ import annotations

import argparse
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from cascade.cli import cmd_impact


class TestImpactGenerate(unittest.TestCase):
    def test_generate_calls_rewrite_once_for_all_source_urns(self):
        urns = ["urn:li:dataset:one", "urn:li:dataset:two"]
        catalog = {"datasets_by_urn": {}, "downstream_map": {}, "column_edges": [], "all_ml_features": [], "all_ml_models": [], "ml_features_by_name": {}, "ml_models_by_feature_urn": {}}
        with tempfile.TemporaryDirectory() as tmp:
            diff = Path(tmp) / "diff.json"
            diff.write_text('[{"type":"FIELD_REMOVED","from":"old"}]')
            args = argparse.Namespace(
                diff=str(diff), config=None, source="fixture", fixture=None,
                models_dir=None, generate=True, rewrite=None, out=None, urn=None,
            )
            stdout = StringIO()
            with mock.patch("cascade.cli._resolve_impact_urns", return_value=urns), \
                 mock.patch("cascade.cli.changes_for_urn", return_value=[{"type": "FIELD_REMOVED", "from": "old"}]), \
                 mock.patch("cascade.cli.resolve_catalog", return_value=catalog), \
                 mock.patch("cascade.cli.choose_and_rewrite", return_value=[]) as rewrite, \
                 redirect_stdout(stdout):
                cmd_impact(args)
        rewrite.assert_called_once()
        self.assertEqual(rewrite.call_args.kwargs["source_urns"], urns)
