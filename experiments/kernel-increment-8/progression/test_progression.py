"""Compatibility entrypoint: progression controls now test the adopted runtime."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tests'))
from test_kernel_progression import ProgressionTests
