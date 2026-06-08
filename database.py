"""
AttendBot — Database
====================
Central database abstraction layer and schema initialization.
"""

import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def execute_query(sql, params=(), *, fetch_one=False, fetch_all=False, commit=False):
    """Run a SQL statement with guaranteed connection cleanup.

    Args:
        sql:        SQL string with %s placeholders.
        params:     Tuple of parameters.
        fetch_one:  Return a single dict row.
        fetch_all:  Return a list of dict rows.
        commit:     Commit the transaction (for INSERT/UPDATE).

    Returns:
        A dict, list of dicts, or None depending on flags.
    """
    conn = psycopg2.connect(DATABASE_URL)
    try:
        use_dict = fetch_one or fetch_all
        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) if use_dict else conn.cursor()
        cur.execute(sql, params)
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        else:
            result = None
        if commit:
            conn.commit()
        cur.close()
        return result
    finally:
        conn.close()


def init_db():
    execute_query("""
        CREATE TABLE IF NOT EXISTS employees (
            telegram_id   BIGINT PRIMARY KEY,
            name          TEXT NOT NULL,
            username      TEXT,
            registered_at TIMESTAMP DEFAULT NOW()
        );
    """, commit=True)
    
    # Safely add the is_active column for existing databases
    try:
        execute_query("ALTER TABLE employees ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE", commit=True)
    except Exception:
        pass
        
    execute_query("""
        CREATE TABLE IF NOT EXISTS attendance (
            id          SERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            date        DATE NOT NULL,
            status      TEXT NOT NULL,
            marked_at   TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(telegram_id, date)
        );
    """, commit=True)

    # Upgrade existing marked_at from TIMESTAMP to TIMESTAMPTZ for correct timezone handling
    try:
        execute_query("ALTER TABLE attendance ALTER COLUMN marked_at TYPE TIMESTAMPTZ", commit=True)
    except Exception:
        pass

    execute_query("""
        CREATE TABLE IF NOT EXISTS holidays (
            date        DATE PRIMARY KEY,
            description TEXT NOT NULL
        );
    """, commit=True)
