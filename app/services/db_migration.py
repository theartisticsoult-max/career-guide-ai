"""One-time, safe copy of legacy SQLite rows into the configured database.

Only runs when ``DATABASE_URL`` is configured (e.g. Render Postgres) and the
target table is empty, so it can never overwrite data already in Postgres.
"""
import os
import sqlite3

from sqlalchemy import text

from app.services.database_config import legacy_sqlite_path

TABLES = (
    'users',
    'psychometric_results',
    'quiz_results',
    'iq_test_results',
    'admin_logs',
)


def copy_legacy_sqlite_data(session, sqlite_path=None):
    """Copy rows from a legacy SQLite file into empty target tables.

    Returns a dict of table name -> number of rows copied.
    """
    if not os.getenv('DATABASE_URL'):
        return {}

    sqlite_path = sqlite_path or legacy_sqlite_path()
    if not os.path.exists(sqlite_path):
        return {}

    source = sqlite3.connect(sqlite_path)
    source.row_factory = sqlite3.Row
    copied = {}

    try:
        for table in TABLES:
            existing = session.execute(text(f'SELECT COUNT(*) FROM {table}')).scalar()
            if existing:
                copied[table] = 0
                continue
            try:
                rows = source.execute(f'SELECT * FROM {table} ORDER BY id').fetchall()
            except sqlite3.OperationalError:
                copied[table] = 0
                continue

            for row in rows:
                values = dict(row)
                columns = ', '.join(values)
                placeholders = ', '.join(f':{name}' for name in values)
                session.execute(
                    text(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'),
                    values,
                )
            copied[table] = len(rows)
        session.commit()
    finally:
        source.close()

    return copied
