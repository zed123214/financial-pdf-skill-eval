"""Ensure FRAMEWORK_ROOT is on sys.path when modules are loaded outside run.py."""
from __future__ import annotations

import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[1]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))
