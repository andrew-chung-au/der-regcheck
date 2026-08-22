"""Database connection management with connection pooling."""
from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


import psycopg2
from psycopg2.pool import SimpleConnectionPool


ROOT = Path(__file__).resolve().parents[2]


def get_database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    return url


_pool: SimpleConnectionPool | None = None


def get_pool() -> SimpleConnectionPool:
    """Get or create a connection pool."""
    global _pool
    if _pool is None:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=get_database_url(),
        )
    return _pool


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    """Get a database connection from the pool."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)