#!/usr/bin/env python3
"""Single entry point for HaulRank system health (brutal live E2E).

Usage:
  python3 scripts/e2e.py
  python3 scripts/e2e.py https://haulrank-pdmh.onrender.com https://haulrank.vercel.app
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    brutal = Path(__file__).resolve().parent / "e2e_brutal.py"
    ns = runpy.run_path(str(brutal))
    raise SystemExit(ns["main"]())
