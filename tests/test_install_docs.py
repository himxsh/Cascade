"""The install command users copy must be plain PyPI, and every command the docs name must exist.

0.1.0 shipped without `cascade setup` while the README told people to run it.
These checks catch that class of drift before merge.
"""

from __future__ import annotations

import contextlib
import io
import re
import unittest
from pathlib import Path
from unittest import mock

from cascade.cli import main

ROOT = Path(__file__).resolve().parents[1]
INSTALL = "pip install cascade-bot"
# Where users read the install command. Action templates pin a commit on purpose.
USER_FACING = (
    ROOT / "README.md",
    ROOT / "frontend" / "src" / "site.ts",
    ROOT / "frontend" / "src" / "Meta.tsx",
)


def _documented_commands() -> set[str]:
    text = (ROOT / "README.md").read_text()
    # `cascade setup`, a line starting with `cascade demo --out …`, a table cell.
    return set(re.findall(r"(?:^|`)cascade ([a-z][a-z-]*)", text, flags=re.MULTILINE))


class TestInstallDocs(unittest.TestCase):
    def test_install_command_is_plain_pypi(self) -> None:
        for path in USER_FACING:
            text = path.read_text()
            with self.subTest(path=path.name):
                self.assertIn(INSTALL, text)
                self.assertNotIn("git+https://github.com/himxsh/Cascade", text)

    def test_readme_names_real_commands(self) -> None:
        commands = _documented_commands()
        self.assertIn("setup", commands)
        for command in sorted(commands):
            with self.subTest(command=command):
                out = io.StringIO()
                with (
                    mock.patch("sys.argv", ["cascade", command, "--help"]),
                    mock.patch("cascade.cli.load_dotenv"),
                    contextlib.redirect_stdout(out),
                    contextlib.redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as exit_,
                ):
                    main()
                self.assertEqual(exit_.exception.code, 0, f"`cascade {command}` is not a command")


if __name__ == "__main__":
    unittest.main()
