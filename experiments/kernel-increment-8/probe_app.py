"""Compatibility launch point for the production Increment 8 acceptance application."""
from pathlib import Path
import runpy
if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).with_name('acceptance_app.py')), run_name='__main__')
