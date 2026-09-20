#!/usr/bin/env python3
"""Increment 8 live acceptance against the production runtime; local inference only."""
from pathlib import Path
import runpy
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'experiments/kernel-increment-8/acceptance.py'), run_name='__main__')
