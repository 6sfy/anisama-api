#!/usr/bin/env python3
"""Entry point for the anisama-api server."""

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.server import main

if __name__ == "__main__":
    main()
