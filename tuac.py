#!/usr/bin/env python3
"""Entry point so `python3 tuac.py ...` works without installing anything."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tua.cli import main

if __name__ == "__main__":
    sys.exit(main())
