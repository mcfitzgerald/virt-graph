"""
Database connectivity for VG/SQL.

Reads DATABASE_URL from environment or .env file.
Uses psycopg (v3) for PostgreSQL connections.

Usage:
    from virt_graph.db import connection

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            print(cur.fetchone())
"""

import os
from contextlib import contextmanager
from pathlib import Path

try:
    import psycopg
except ImportError:
    psycopg = None  # type: ignore[assignment]


def _load_dotenv() -> None:
    """Load .env file from project root into os.environ (if not already set)."""
    # Walk up from this file to find .env
    current = Path(__file__).resolve().parent
    for _ in range(5):  # max 5 levels up
        env_path = current / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # Don't override existing env vars
                    if key not in os.environ:
                        os.environ[key] = value
            return
        current = current.parent


def get_database_url() -> str:
    """Get DATABASE_URL from environment, loading .env if needed."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        _load_dotenv()
        url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. "
            "Set it in your environment or create a .env file. "
            "See .env.example for format."
        )
    return url


def _require_psycopg():
    if psycopg is None:
        raise ImportError(
            "psycopg is required for database access. "
            "Install with: pip install virt-graph[db]"
        )


def get_connection(conninfo: str | None = None, **kwargs) -> "psycopg.Connection":
    """
    Open a PostgreSQL connection.

    Args:
        conninfo: Connection string. Defaults to DATABASE_URL from environment.
        **kwargs: Additional arguments passed to psycopg.connect().

    Returns:
        psycopg.Connection
    """
    _require_psycopg()
    if conninfo is None:
        conninfo = get_database_url()
    return psycopg.connect(conninfo, **kwargs)


@contextmanager
def connection(conninfo: str | None = None, **kwargs):
    """
    Context manager for a PostgreSQL connection.

    Commits on clean exit, rolls back on exception, always closes.

    Args:
        conninfo: Connection string. Defaults to DATABASE_URL from environment.
        **kwargs: Additional arguments passed to psycopg.connect().

    Yields:
        psycopg.Connection
    """
    conn = get_connection(conninfo, **kwargs)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
