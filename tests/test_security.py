"""Tests for Phase 1 security hardening."""
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import check_password_hash

from app import app, db, limiter
from app.models import Database

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates'


def csrf_token_from_page(client, path='/login'):
    html = client.get(path).data.decode('utf-8', 'replace')
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    assert match, f'No CSRF token meta tag found on {path}'
    return match.group(1)


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        limiter.reset()
        app.config['RATELIMIT_ENABLED'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def tearDown(self):
        limiter.reset()
        app.config['WTF_CSRF_ENABLED'] = False


class TestAdminBootstrap(SecurityTestCase):
    def test_admin_created_only_from_complete_env(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {}, clear=True):
                empty = Database(os.path.join(directory, 'empty.db'))
                conn = empty.get_connection()
                count = conn.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1').fetchone()[0]
                conn.close()
                self.assertEqual(count, 0)

            with patch.dict(os.environ, {
                'ADMIN_USERNAME': 'envadmin',
                'ADMIN_EMAIL': 'envadmin@example.com',
                'ADMIN_PASSWORD': 'a-strong-password',
            }, clear=True):
                seeded = Database(os.path.join(directory, 'seeded.db'))
                admin = seeded.get_user_by_username('envadmin')
                self.assertIsNotNone(admin)
                self.assertEqual(admin['is_admin'], 1)
                self.assertNotEqual(admin['password'], hashlib.sha256(b'a-strong-password').hexdigest())
                self.assertTrue(check_password_hash(admin['password'], 'a-strong-password'))


class TestSecretKey(SecurityTestCase):
    def test_secret_key_required_in_production(self):
        env = os.environ.copy()
        env.pop('SECRET_KEY', None)
        env['FLASK_DEBUG'] = '0'
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            [sys.executable, '-c', 'import app'],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY', result.stderr)

    def test_debug_flag_comes_from_env(self):
        env = os.environ.copy()
        env['SECRET_KEY'] = 'test-secret-key'
        env['FLASK_DEBUG'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run(
            [sys.executable, '-c', 'from app import app; print(app.config["DEBUG"])'],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().splitlines()[-1], 'True')


class TestPasswordHashing(SecurityTestCase):
    def _remove_user(self, username):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()

    def test_new_users_use_werkzeug_hash(self):
        username = 'hashuser_security'
        self._remove_user(username)
        db.create_user(username, f'{username}@example.com', 'password123')
        stored = db.get_user_by_username(username)['password']
        self.assertNotEqual(stored, hashlib.sha256(b'password123').hexdigest())
        self.assertTrue(check_password_hash(stored, 'password123'))

    def test_legacy_sha256_hash_upgrades_on_successful_login(self):
        username = 'legacyuser_security'
        self._remove_user(username)
        legacy = hashlib.sha256(b'password123').hexdigest()
        conn = db.get_connection()
        conn.execute(
            'INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, 0)',
            (username, f'{username}@example.com', legacy),
        )
        conn.commit()
        conn.close()

        response = self.client.post('/login', data={
            'username': username,
            'password': 'password123',
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        upgraded = db.get_user_by_username(username)['password']
        self.assertNotEqual(upgraded, legacy)
        self.assertTrue(check_password_hash(upgraded, 'password123'))

        with self.client.session_transaction() as session:
            session.clear()
        second = self.client.post('/login', data={
            'username': username,
            'password': 'password123',
        }, follow_redirects=True)
        self.assertEqual(second.status_code, 200)

    def test_wrong_legacy_password_does_not_upgrade(self):
        username = 'legacywrong_security'
        self._remove_user(username)
        legacy = hashlib.sha256(b'correct-password').hexdigest()
        conn = db.get_connection()
        conn.execute(
            'INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, 0)',
            (username, f'{username}@example.com', legacy),
        )
        conn.commit()
        conn.close()

        self.client.post('/login', data={
            'username': username,
            'password': 'wrong-password',
        })
        self.assertEqual(db.get_user_by_username(username)['password'], legacy)


class TestCSRF(SecurityTestCase):
    def setUp(self):
        super().setUp()
        app.config['WTF_CSRF_ENABLED'] = True

    def test_login_requires_csrf_token(self):
        response = self.client.post('/login', data={
            'username': 'someone',
            'password': 'password',
        })
        self.assertEqual(response.status_code, 400)

        token = csrf_token_from_page(self.client)
        response = self.client.post('/login', data={
            'username': 'someone',
            'password': 'password',
        }, headers={'X-CSRFToken': token})
        self.assertNotEqual(response.status_code, 400)

    def test_chatbot_api_requires_header_token(self):
        token = csrf_token_from_page(self.client, '/chatbot')
        rejected = self.client.post('/api/chatbot', json={'message': 'hello'})
        self.assertEqual(rejected.status_code, 400)
        accepted = self.client.post(
            '/api/chatbot', json={'message': 'hello'}, headers={'X-CSRFToken': token}
        )
        self.assertEqual(accepted.status_code, 200)

    def test_logout_is_post_only_and_protected(self):
        self.assertEqual(self.client.get('/logout').status_code, 405)
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['username'] = 'test'
        token = csrf_token_from_page(self.client, '/')
        response = self.client.post('/logout', headers={'X-CSRFToken': token})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn('user_id', session)


class TestTemplateSecurity(SecurityTestCase):
    def test_no_unsafe_summary_rendering_and_escaped_insertions(self):
        admin_user = (TEMPLATES / 'admin_user.html').read_text(encoding='utf-8')
        career = (TEMPLATES / 'career.html').read_text(encoding='utf-8')
        compare = (TEMPLATES / 'compare.html').read_text(encoding='utf-8')
        base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')

        self.assertNotIn('ai_summary|safe', admin_user)
        self.assertIn('answerDiv.textContent', career)
        self.assertIn('escapeHtml(', compare)
        self.assertIn('X-CSRFToken', base)

    def test_all_target_blank_links_have_noopener(self):
        pattern = re.compile(r'<a\b[^>]*target="_blank"[^>]*>', re.IGNORECASE)
        for path in TEMPLATES.glob('*.html'):
            for tag in pattern.findall(path.read_text(encoding='utf-8')):
                self.assertIn('rel="noopener noreferrer"', tag, path.name)


class TestApiErrorsAndLimits(SecurityTestCase):
    def test_api_errors_are_logged_not_returned(self):
        username = 'erroruser_security'
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        db.create_user(username, f'{username}@example.com', 'password123')
        user = db.get_user_by_username(username)
        with self.client.session_transaction() as session:
            session['user_id'] = user['id']

        with patch('app.blueprints.api.submit_quiz', side_effect=RuntimeError('secret detail')):
            response = self.client.post('/api/quiz/submit', json={})

        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'secret detail', response.data)
        self.assertIn('Internal server error', response.get_json()['error'])

    def test_login_rate_limit(self):
        statuses = [
            self.client.post('/login', data={'username': 'x', 'password': 'y'}).status_code
            for _ in range(6)
        ]
        self.assertEqual(statuses[:5], [200] * 5)
        self.assertEqual(statuses[5], 429)

    def test_chatbot_rate_limit(self):
        statuses = [
            self.client.post('/api/chatbot', json={'message': 'hello'}).status_code
            for _ in range(21)
        ]
        self.assertEqual(statuses[:20], [200] * 20)
        self.assertEqual(statuses[20], 429)


if __name__ == '__main__':
    unittest.main()
