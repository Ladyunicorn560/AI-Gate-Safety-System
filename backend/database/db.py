"""
Database connection manager for AI Gate Safety System.
Uses pyodbc with Microsoft SQL Server (Windows Authentication).
Mirrors the pattern from Business Analyst project.
"""

import pyodbc
import logging
import time
from contextlib import contextmanager
from backend.config import DB_CONNECTION_STRING, DB_POOL_SIZE, DB_TIMEOUT

logger = logging.getLogger(__name__)

# ─── Simple Connection Pool ───────────────────────────────────────────────────
_pool: list = []
_pool_in_use: list = []


def _create_connection() -> pyodbc.Connection:
    """Create a new pyodbc connection with retry logic."""
    for attempt in range(3):
        try:
            conn = pyodbc.connect(DB_CONNECTION_STRING, timeout=DB_TIMEOUT)
            conn.autocommit = False
            return conn
        except pyodbc.Error as e:
            logger.warning(f"DB connection attempt {attempt + 1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2)
    raise ConnectionError("Could not connect to SQL Server after 3 attempts.")


def initialize_db():
    """Initialize the connection pool on startup."""
    global _pool
    logger.info(f"Connecting to SQL Server: {DB_CONNECTION_STRING[:60]}...")
    try:
        for _ in range(3):  # Pre-create 3 connections
            _pool.append(_create_connection())
        logger.info(f"✅ SQL Server pool initialized ({len(_pool)} connections). DB: AI_Gate_Safety_DB")
    except Exception as e:
        logger.error(f"❌ Failed to initialize DB pool: {e}")
        raise


def get_connection() -> pyodbc.Connection:
    """Get a connection from the pool or create a new one."""
    if _pool:
        conn = _pool.pop()
        _pool_in_use.append(conn)
        return conn
    # Pool empty — create new connection
    conn = _create_connection()
    _pool_in_use.append(conn)
    return conn


def release_connection(conn: pyodbc.Connection):
    """Return a connection to the pool."""
    if conn in _pool_in_use:
        _pool_in_use.remove(conn)
    if len(_pool) < DB_POOL_SIZE:
        _pool.append(conn)
    else:
        conn.close()


@contextmanager
def get_db():
    """Context manager for safe DB access — auto-commits or rolls back."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB transaction rolled back: {e}")
        raise
    finally:
        cursor.close()
        release_connection(conn)


def check_health() -> dict:
    """Check database connectivity and return status."""
    try:
        with get_db() as cursor:
            cursor.execute("SELECT 1 AS Health, DB_NAME() AS DBName, @@SERVERNAME AS Server")
            row = cursor.fetchone()
            return {
                "status": "healthy",
                "database": row.DBName,
                "server":   row.Server,
            }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def close_all():
    """Close all connections in pool — call on app shutdown."""
    for conn in _pool + _pool_in_use:
        try:
            conn.close()
        except Exception:
            pass
    _pool.clear()
    _pool_in_use.clear()
    logger.info("All DB connections closed.")
