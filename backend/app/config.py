"""Configuration. Secrets come from the environment, never from source (SRS 17.2, SEC, Appendix B #16)."""
import logging
import os
import secrets

log = logging.getLogger("crimemind")


def _load_dotenv() -> None:
    """Tiny .env loader (no dependency). Real environment variables always win; the file is git-ignored."""
    path = os.environ.get("CM_ENV_FILE") or os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip().removeprefix("export ").strip(), v.strip().strip("'\""))
    except OSError:
        pass


_load_dotenv()

DATABASE_URL = os.environ.get("CM_DATABASE_URL", "postgresql://cm_app:cm_app_dev@localhost:5432/crimemind")
ADMIN_DATABASE_URL = os.environ.get("CM_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/crimemind")

_jwt = os.environ.get("CM_JWT_SECRET")
if not _jwt:
    # Development convenience only: tokens do not survive a restart. Set CM_JWT_SECRET in any real deployment.
    _jwt = secrets.token_urlsafe(48)
    log.warning("CM_JWT_SECRET is not set; using an ephemeral secret (tokens reset on restart).")
JWT_SECRET = _jwt
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(os.environ.get("CM_JWT_TTL_MINUTES", "480"))

CORS_ORIGINS = [o for o in os.environ.get("CM_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]

# Optional LLM. Without a key the AI layer reports itself as the offline template provider (SRS 13.21).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("CM_AI_MODEL", "claude-sonnet-5-5")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("CM_GEMINI_MODEL", "gemini-3.5-flash-lite")
# auto (default: Anthropic key, else Gemini key, else offline) | anthropic | gemini | offline
AI_PROVIDER = os.environ.get("CM_AI_PROVIDER", "auto").lower()
AI_TIMEOUT_SECONDS = float(os.environ.get("CM_AI_TIMEOUT", "30"))
AI_MAX_RETRIES = int(os.environ.get("CM_AI_MAX_RETRIES", "2"))
AI_RETRY_BASE_WAIT = float(os.environ.get("CM_AI_RETRY_BASE_WAIT", "0.5"))
AI_RETRY_MAX_WAIT = float(os.environ.get("CM_AI_RETRY_MAX_WAIT", "8"))

QUERY_TIMEOUT_MS = int(os.environ.get("CM_QUERY_TIMEOUT_MS", "5000"))
APP_VERSION = "1.0.0"
