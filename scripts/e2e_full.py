#!/usr/bin/env python3
"""Deprecated entry — redirects to the post-deploy PUNISH suite."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) == 2:
        sys.argv.append("http://127.0.0.1:5173")
    target = Path(__file__).resolve().parent / "e2e_punish.py"
    ns = runpy.run_path(str(target))
    raise SystemExit(ns["main"]())
