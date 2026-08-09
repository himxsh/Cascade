"""Self-check for stdlib .env loader."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cascade.dotenv_load import load_dotenv


class TestLoadDotenv(unittest.TestCase):
    def test_loads_and_does_not_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "# comment\n"
                "FOO_CASCADE_TEST=from_file\n"
                "BAR_CASCADE_TEST=keep_me\n"
                'QUOTED_CASCADE_TEST="hello world"\n'
            )
            with mock.patch.dict(os.environ, {"BAR_CASCADE_TEST": "already"}, clear=False):
                os.environ.pop("FOO_CASCADE_TEST", None)
                os.environ.pop("QUOTED_CASCADE_TEST", None)
                loaded = load_dotenv(env_path)
                self.assertEqual(loaded, env_path.resolve())
                self.assertEqual(os.environ["FOO_CASCADE_TEST"], "from_file")
                self.assertEqual(os.environ["BAR_CASCADE_TEST"], "already")
                self.assertEqual(os.environ["QUOTED_CASCADE_TEST"], "hello world")
            for k in ("FOO_CASCADE_TEST", "QUOTED_CASCADE_TEST"):
                os.environ.pop(k, None)


if __name__ == "__main__":
    unittest.main()
