"""Password hashing and JWT handling (SRS 17.2)."""
import time

import bcrypt
import jwt

from . import config

# Pre-computed hash so unknown-user logins cost the same as known-user ones (no account enumeration).
_DUMMY = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=10))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    target = hashed.encode() if hashed else _DUMMY
    ok = bcrypt.checkpw(password.encode(), target)
    return ok and hashed is not None


def make_token(username: str, role: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": username, "role": role, "iat": now, "exp": now + config.JWT_TTL_MINUTES * 60},
                      config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
