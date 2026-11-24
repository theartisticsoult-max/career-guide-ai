"""Tests for Phase 3: SQLAlchemy models, migrations and legacy data copy."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from werkzeug.security import check_password_hash

from app import app, db
from app.extensions import sqlalchemy as sa_extension
from app.models import BaseModel
from app.services.database_config import build_database_uri, legacy_sqlite_path
from app.services.db_migration import copy_legacy_sqlite_data

ROOT = Path(__file__).resolve().parents[1]


class Phase3TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _new_user(self, username='phase3user'):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        created = db.create_user(username, f'{username}@example.com', 'password123')
        self.assertTrue(created['success'], created)
        return db.get_user_by_username(username)


class TestDatabaseUri(Phase3TestCase):
    def test_database_url_is_normalised(self):
        with patch.dict(os.environ, {'DATABASE_URL': 'postgres://user:pass@host:5432/career'}, clear=False):
            self.assertEqual(
                build_database_uri(), 'postgresql://user:pass@host:5432/career'
            )
        with patch.dict(os.environ, {'DATABASE_URL': 'postgresql://user:pass@host/db'}, clear=False):
            self.assertEqual(build_database_uri(), 'postgresql://user:pass@host/db')

    def test_sqlite_path_is_absolute_and_env_configurable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('DATABASE_URL', None)
            with tempfile.TemporaryDirectory() as directory:
                path = os.path.join(directory, 'test.db')
                os.environ['DATABASE_PATH'] = path
                uri = build_database_uri()
                self.assertTrue(uri.startswith('sqlite:///'))
                self.assertIn(path.replace('\\', '/'), uri)
        self.assertTrue(os.path.isabs(db.db_path))


class TestSchemaAndFacade(Phase3TestCase):
    def test_tables_and_columns_match_original_schema(self):
        with app.app_context():
            inspector = inspect(sa_extension.engine)
        expected = {
            'users': {
                'id', 'username', 'email', 'password', 'full_name', 'phone',
                'education', 'stream', 'created_at', 'last_login', 'is_admin',
            },
            'psychometric_results': {
                'id', 'user_id', 'test_date', 'personality', 'interests',
                'aptitudes', 'work_styles', 'value_data', 'raw_answers',
                'ai_summary', 'career_matches',
            },
            'quiz_results': {
                'id', 'user_id', 'test_date', 'answers', 'recommendations', 'ai_summary',
            },
            'iq_test_results': {
                'id', 'user_id', 'test_date', 'iq_score', 'correct_count',
                'section_scores', 'answers', 'time_taken',
            },
            'admin_logs': {
                'id', 'admin_id', 'action', 'target_user_id', 'timestamp',
            },
        }
        for table, columns in expected.items():
            with self.subTest(table=table):
                actual = {column['name'] for column in inspector.get_columns(table)}
                self.assertEqual(actual, columns)

    def test_foreign_keys_enabled_and_cascade_deletes(self):
        with app.app_context():
            inspector = inspect(sa_extension.engine)
        for table in ('psychometric_results', 'quiz_results', 'iq_test_results', 'admin_logs'):
            with self.subTest(table=table):
                keys = inspector.get_foreign_keys(table)
                self.assertTrue(keys)
                self.assertEqual(keys[0]['options'].get('ondelete'), 'CASCADE')

        user = self._new_user('cascadeuser')
        user_id = user['id']
        db.save_quiz_result(user_id, {'a': 1}, ['C001'], 'summary')
        db.save_psychometric_result(
            user_id, {'R': 1}, {}, {}, {}, {}, {}, 'summary', ['C001']
        )
        db.save_iq_test_result(user_id, 110, 20, {'logical': 90}, {}, 60)
        db.log_admin_action(user_id, 'test action')

        conn = db.get_connection()
        self.assertEqual(conn.execute(
            'SELECT COUNT(*) FROM quiz_results WHERE user_id = ?', (user_id,)
        ).fetchone()[0], 1)
        conn.close()

        db.delete_user(user_id)
        self.assertIsNone(db.get_user_by_id(user_id))
        conn = db.get_connection()
        for table, column in (
            ('quiz_results', 'user_id'),
            ('psychometric_results', 'user_id'),
            ('iq_test_results', 'user_id'),
            ('admin_logs', 'admin_id'),
        ):
            self.assertEqual(
                conn.execute(f'SELECT COUNT(*) FROM {table} WHERE {column} = ?', (user_id,)).fetchone()[0],
                0,
            )
        conn.close()

    def test_all_facade_methods_preserve_behavior(self):
        user = self._new_user('facadeuser')
        user_id = user['id']
        self.assertTrue(check_password_hash(user['password'], 'password123'))
        self.assertIsNotNone(db.authenticate_user('facadeuser', 'password123'))
        self.assertIsNone(db.authenticate_user('facadeuser', 'wrong'))

        db.update_user(user_id, full_name='Facade User', phone='999', education='College')
        self.assertEqual(db.get_user_by_id(user_id)['full_name'], 'Facade User')
        self.assertEqual(len(db.get_all_users()), len(db.get_all_users(admin_only=False)))

        quiz_id = db.save_quiz_result(user_id, {'q1': 'a'}, [{'id': 'C001'}], 'quiz summary')
        psycho_id = db.save_psychometric_result(
            user_id, {'R': 5}, {'I': 4}, {'logical': 3}, {'team': 2}, {'risk': 1},
            {'q1': 2}, 'psycho summary', [{'id': 'C001'}]
        )
        iq_id = db.save_iq_test_result(user_id, 120, 24, {'logical': 90}, {'q1': 1}, 100)
        self.assertGreater(quiz_id, 0)
        self.assertGreater(psycho_id, 0)
        self.assertGreater(iq_id, 0)

        quiz = db.get_quiz_results(user_id)[0]
        self.assertEqual(quiz['answers'], {'q1': 'a'})
        self.assertEqual(quiz['recommendations'], [{'id': 'C001'}])
        psycho = db.get_psychometric_results(user_id)[0]
        self.assertEqual(psycho['personality'], {'R': 5})
        self.assertEqual(psycho['career_matches'], [{'id': 'C001'}])
        iq = db.get_latest_iq_test_result(user_id)
        self.assertEqual(iq['section_scores'], {'logical': 90})
        stats = db.get_iq_test_stats(user_id)
        self.assertEqual(stats['total_tests'], 1)
        self.assertEqual(stats['avg_score'], 120)
        self.assertEqual(db.get_stats()['iq_tests'], db.get_stats()['iq_tests'])

        db.log_admin_action(user_id, 'viewed user', user_id)
        logs = db.get_admin_logs()
        self.assertTrue(any(log['action'] == 'viewed user' for log in logs))


class TestLegacyCopyAndMigrations(Phase3TestCase):
    def test_legacy_sqlite_copy_is_safe_and_idempotent(self):
        source_path = db.db_path
        self.assertTrue(os.path.exists(source_path))
        with tempfile.TemporaryDirectory() as directory:
            target_path = os.path.join(directory, 'postgres_standin.db')
            engine = create_engine(f'sqlite:///{target_path}', poolclass=NullPool)
            BaseModel.metadata.create_all(engine)
            session = sessionmaker(bind=engine)()

            with patch.dict(os.environ, {
                'DATABASE_URL': 'postgresql://user:pass@localhost/career',
                'LEGACY_DATABASE_PATH': source_path,
            }):
                copied = copy_legacy_sqlite_data(session, source_path)
                self.assertGreater(copied['users'], 0)
                again = copy_legacy_sqlite_data(session, source_path)
                self.assertEqual(again['users'], 0)

            user_count = session.execute(
                text('SELECT COUNT(*) FROM users')
            ).scalar()
            self.assertEqual(user_count, copied['users'])
            session.close()
            engine.dispose()

    def test_migration_upgrade_creates_schema_on_fresh_database(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = os.path.join(directory, 'migrated.db')
            env = os.environ.copy()
            env.update({
                'FLASK_APP': 'app',
                'SECRET_KEY': 'migration-test-key',
                'SKIP_DB_CREATE': '1',
                'DATABASE_PATH': db_path,
                'PYTHONIOENCODING': 'utf-8',
            })
            env.pop('DATABASE_URL', None)
            result = subprocess.run(
                [sys.executable, '-m', 'flask', 'db', 'upgrade'],
                cwd=ROOT, env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            engine = create_engine(f'sqlite:///{db_path}', poolclass=NullPool)
            self.assertTrue(inspect(engine).has_table('users'))
            self.assertTrue(inspect(engine).has_table('quiz_results'))
            engine.dispose()

    def test_migrations_directory_is_present(self):
        self.assertTrue((ROOT / 'migrations' / 'env.py').exists())
        self.assertTrue(any((ROOT / 'migrations' / 'versions').glob('*_*.py')))


if __name__ == '__main__':
    unittest.main()
