#!/usr/bin/env python3
"""Run the full unit-test suite from the project root."""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.exit(subprocess.call(
    [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=ROOT))
