import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "backend"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
os.environ.setdefault("CM_JWT_SECRET", "research-tests-not-a-secret")
os.environ["CM_AI_PROVIDER"] = "offline"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("ANTHROPIC_API_KEY", None)
