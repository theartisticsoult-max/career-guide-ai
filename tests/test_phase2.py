"""Tests for Phase 2: route coverage, cleanup and kept-screen fixes."""
import json
import os
import re
import sys
import unittest
from pathlib import Path

from app import app, db
from app.services.career_data import get_recommendations

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'


class Phase2TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _create_user(self, username, admin=False):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        db.create_user(username, f'{username}@example.com', 'password123')
        if admin:
            conn = db.get_connection()
            conn.execute('UPDATE users SET is_admin = 1 WHERE username = ?', (username,))
            conn.commit()
            conn.close()
        return db.get_user_by_username(username)


class TestEveryPageRenders(Phase2TestCase):
    def test_all_pages_render_for_logged_out_user_and_admin(self):
        regular = self._create_user('routeuser_phase2')
        admin = self._create_user('routeadmin_phase2', admin=True)

        public_pages = [
            '/', '/categories', '/category/Healthcare', '/chatbot', '/compare',
            '/career/C001', '/resources', '/health', '/login', '/register',
            '/api/categories', '/api/all-careers', '/api/featured-careers',
            '/api/career/C001', '/api/search?q=engineer', '/api/category/Healthcare',
        ]
        user_pages = [
            '/dashboard', '/quiz', '/psychometric-test', '/results',
            '/psychometric-results', '/iq-test', '/iq-test-results',
        ]
        admin_pages = ['/admin', f'/admin/user/{admin["id"]}']

        for path in public_pages:
            with self.subTest(role='logged-out', path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

        with self.client.session_transaction() as session:
            session['user_id'] = regular['id']
            session['username'] = regular['username']
            session['is_admin'] = 0
        for path in user_pages:
            with self.subTest(role='user', path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

        with self.client.session_transaction() as session:
            session['user_id'] = admin['id']
            session['username'] = admin['username']
            session['is_admin'] = 1
        for path in admin_pages:
            with self.subTest(role='admin', path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)


class TestKeptScreenFixes(Phase2TestCase):
    def test_compare_honors_shared_ids(self):
        response = self.client.get('/compare?ids=C001,C002,does-not-exist')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        match = re.search(r'const serverSelectedIds = (\[.*?\]);', html)
        self.assertIsNotNone(match)
        self.assertEqual(json.loads(match.group(1)), ['C001', 'C002'])

    def test_template_fixes_are_present(self):
        compare = (TEMPLATES / 'compare.html').read_text(encoding='utf-8')
        career = (TEMPLATES / 'career.html').read_text(encoding='utf-8')
        index = (TEMPLATES / 'index.html').read_text(encoding='utf-8')
        self.assertIn('function showToast(', compare)
        self.assertIn('careerName', career)
        self.assertNotIn('${career.Career_Name}', career)
        self.assertIn('if (!container) return;', index)

    def test_dead_links_are_removed_and_resources_is_served(self):
        for name in ('login.html', 'register.html', 'admin_dashboard.html'):
            text = (TEMPLATES / name).read_text(encoding='utf-8')
            for dead in ('/forgot-password', '/terms', '/privacy', '/admin/users'):
                self.assertNotIn(f'href="{dead}"', text, name)
        self.assertEqual(self.client.get('/resources').status_code, 200)


class TestCleanupAndDeployment(Phase2TestCase):
    def test_database_path_is_absolute_and_env_configurable(self):
        self.assertTrue(os.path.isabs(db.db_path))
        self.assertEqual(db.db_path, os.path.abspath(os.environ['DATABASE_PATH']))

    def test_utils_removed_and_legacy_alias_gone(self):
        self.assertFalse((ROOT / 'utils').exists())
        self.assertNotIn('chatbot_service', sys.modules)

    def test_recommendations_are_deterministic(self):
        first = get_recommendations({})
        second = get_recommendations({})
        self.assertEqual(first, second)
        self.assertTrue(all(rec['match_score'] == 50.0 for rec in first))

    def test_deployment_files_align(self):
        dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
        render = (ROOT / 'render.yaml').read_text(encoding='utf-8')
        requirements = (ROOT / 'requirements.txt').read_text(encoding='utf-8')
        self.assertIn('FROM python:3.11', dockerfile)
        self.assertIn('wsgi:app', dockerfile)
        self.assertIn('${PORT}', dockerfile)
        self.assertIn('HEALTHCHECK', dockerfile)
        self.assertIn('startCommand: gunicorn wsgi:app --bind 0.0.0.0:$PORT', render)
        self.assertIn('healthCheckPath: /health', render)
        self.assertIn('PYTHON_VERSION', render)
        for unused in ('Flask-CORS', 'flask-session', 'joblib'):
            self.assertNotIn(unused, requirements)


if __name__ == '__main__':
    unittest.main()
