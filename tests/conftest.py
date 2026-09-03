from pathlib import Path

# Ensure pytest can import the backend package
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
