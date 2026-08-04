#!/usr/bin/env python3
"""Build the Vite UI into public/ for Vercel static CDN + FastAPI."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PUBLIC = ROOT / "public"


def main() -> None:
    subprocess.check_call(["npm", "ci"], cwd=FRONTEND)
    subprocess.check_call(["npm", "run", "build"], cwd=FRONTEND)
    if PUBLIC.exists():
        shutil.rmtree(PUBLIC)
    shutil.copytree(FRONTEND / "dist", PUBLIC)
    print(f"Copied {FRONTEND / 'dist'} → {PUBLIC}", file=sys.stderr)


if __name__ == "__main__":
    main()
