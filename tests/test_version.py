import tomllib
import unittest
from pathlib import Path

from cascade import __version__


class TestVersion(unittest.TestCase):
    def test_package_version_matches_pyproject(self) -> None:
        # publish.yml uploads the pyproject version; `cascade --version` reports this one.
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        with pyproject.open("rb") as handle:
            expected = tomllib.load(handle)["project"]["version"]
        self.assertEqual(__version__, expected)


if __name__ == "__main__":
    unittest.main()
