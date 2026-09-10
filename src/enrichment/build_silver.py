#!/usr/bin/env python3
"""Build shared silver layer: questions.parquet + prompts.parquet."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENRICHMENT = Path(__file__).resolve().parent


def run(script: str) -> None:
    cmd = [sys.executable, str(ENRICHMENT / script)]
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    run("build_questions.py")
    run("build_prompts.py")
    print("Silver commun prêt:", ROOT / "silver")


if __name__ == "__main__":
    main()
