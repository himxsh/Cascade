#!/usr/bin/env python3
"""Build the Vite UI into api/static/ (function bundle) and public/ (CDN)."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PUBLIC = ROOT / "public"
API_STATIC = ROOT / "api" / "static"


def _copy(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    print(f"Copied {src} → {dest}", file=sys.stderr)


def main() -> None:
    subprocess.check_call(["npm", "ci"], cwd=FRONTEND)
    subprocess.check_call(["npm", "run", "build"], cwd=FRONTEND)
    dist = FRONTEND / "dist"
    _copy(dist, API_STATIC)
    _copy(dist, PUBLIC)


if __name__ == "__main__":
    main()
