"""Research Platform Package."""
import sys
from pathlib import Path

# Ensure ROOT (crimemind/) is on sys.path so that 'research.*' and 'app.*' resolve cleanly
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
