"""Resolve the SQLAlchemy database URI from the environment."""
import os
from pathlib import Path


def build_database_uri():
    """Return a SQLAlchemy URI: DATABASE_URL when set, SQLite otherwise.

    Render supplies ``postgres://...``; SQLAlchemy 2.x expects
    ``postgresql://...``, so normalise that prefix.
    """
    url = os.getenv('DATABASE_URL')
    if url:
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        return url

    db_path = os.getenv('DATABASE_PATH', 'instance/career_guide.db')
    db_path = os.path.abspath(db_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return 'sqlite:///' + Path(db_path).as_posix()


def legacy_sqlite_path():
    """Path to a pre-migration SQLite file that may hold existing data."""
    configured = os.getenv('LEGACY_DATABASE_PATH')
    if configured:
        return os.path.abspath(configured)
    return os.path.abspath('instance/career_guide.db')
