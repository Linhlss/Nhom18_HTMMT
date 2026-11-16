#!/usr/bin/python3
"""Start the persistent topology (networkctl provides lifecycle/control commands)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from control.networkctl import main

if __name__ == '__main__':
    if len(sys.argv) == 1 or sys.argv[1].startswith('--'):
        sys.argv.insert(1, 'start')
    sys.exit(main())
