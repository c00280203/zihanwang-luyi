"""Run isolated integration checks; does not modify demonstration records."""
import subprocess
import sys
from pathlib import Path
if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=Path(__file__).parent))
