"""Shared test setup: isolated database and secret before importing the app."""
import os
import shutil
import tempfile

import pytest

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
# Keep tests deterministic: no live provider calls by default.
os.environ['GROQ_API_KEY'] = ''
_TEMP_DIR = tempfile.mkdtemp(prefix='career-guide-tests-')
os.environ['DATABASE_PATH'] = os.path.join(_TEMP_DIR, 'career_guide.db')


@pytest.fixture(scope='session', autouse=True)
def _cleanup_temp_database():
    yield
    shutil.rmtree(_TEMP_DIR, ignore_errors=True)
