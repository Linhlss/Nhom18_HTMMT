#!/usr/bin/python3
"""Compatibility entry point: operator-approved Apply/Ignore via networkctl."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from control.networkctl import main

if __name__ == '__main__':
    sys.argv.insert(1, 'apply')
    sys.exit(main())
