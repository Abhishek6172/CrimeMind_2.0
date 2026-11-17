"""Connection pool and helpers."""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None


def init_pool(url: str | None = None) -> ConnectionPool:
    global _pool
    if _pool is not None:
        _pool.close()
    _pool = ConnectionPool(url or config.DATABASE_URL, min_size=1, max_size=10,
                           kwargs={"row_factory": dict_row}, open=True, timeout=10)
    return _pool


def pool() -> ConnectionPool:
    if _pool is None:
        init_pool()
    return _pool  # type: ignore[return-value]


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection(actor: str | None = None):
    """A transaction. `actor` is exposed to DB triggers/functions as app.user (audit + EVLM)."""
    with pool().connection() as conn:
        if actor:
            conn.execute("SELECT set_config('app.user', %s, true)", (actor,))
        yield conn


def admin_connect() -> psycopg.Connection:
    return psycopg.connect(config.ADMIN_DATABASE_URL, row_factory=dict_row, autocommit=False)
