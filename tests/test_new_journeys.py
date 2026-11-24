"""Tests for the DISCOVER -> EXPLORE -> CHOOSE -> GROW entry points."""
import unittest
from pathlib import Path
from unittest.mock import patch

from app import app, db
from app.services import profile_service, recommendation_service

ROOT = Path(__file__).resolve().parent.parent


class NewJourneysTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        groq_patch = patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=None,
        )
        groq_patch.start()
        self.addCleanup(groq_patch.stop)

    def _new_user(self, username):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        created = db.create_user(username, f'{username}@example.com', 'password123')
        self.assertTrue(created['success'])
        user = db.get_user_by_username(username)
        with self.client.session_transaction() as session:
            session['user_id'] = user['id']
            session['username'] = username
            session['is_admin'] = 0
        return user

    def test_discover_page_browses_and_searches(self):
        response = self.client.get('/discover')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        self.assertIn('I Know What I Want', html)
        self.assertIn('Help Me Discover My Career', html)
        self.assertIn('/category/Healthcare', html)

        searched = self.client.get('/discover?q=Doctor')
        self.assertEqual(searched.status_code, 200)
        self.assertIn('Careers matching', searched.data.decode('utf-8', 'replace'))

    def test_direct_choice_works_without_assessment(self):
        user = self._new_user('direct_choice_user')
        response = self.client.post('/career/C001/choose', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/roadmap', response.location)
        with app.app_context():
            chosen = recommendation_service.get_chosen_career(user['id'])
            self.assertEqual(chosen['career_id'], 'C001')
        roadmap_html = self.client.get('/roadmap').data.decode('utf-8', 'replace')
        self.assertIn('Roadmap', roadmap_html)

    def test_direct_choice_rejects_unknown_career(self):
        self._new_user('bad_choice_user')
        response = self.client.post('/career/NOPE/choose')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/career/NOPE', response.location)

    def test_dashboard_shows_two_paths_and_current_state(self):
        self._new_user('dashboard_paths_user')
        html = self.client.get('/dashboard').data.decode('utf-8', 'replace')
        self.assertIn('I Know What I Want', html)
        self.assertIn('Help Me Discover My Career', html)
        self.assertNotIn('Psychometric Assessment', html)
        self.assertNotIn('Career Quiz', html)
        self.assertNotIn('IQ Test', html)

        self.client.post('/career/C001/choose')
        chosen_html = self.client.get('/dashboard').data.decode('utf-8', 'replace')
        self.assertIn('Selected career:', chosen_html)
        self.assertIn('Roadmap progress:', chosen_html)
        self.assertIn('Next milestone:', chosen_html)

    def test_primary_navigation_uses_new_labels(self):
        base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
        for label in ('Dashboard', 'Discover Careers', 'My Recommendations',
                      'My Roadmap', 'AI Career Mentor', 'Profile &amp; Settings'):
            self.assertIn(label, base)
        for legacy in ('/quiz', '/psychometric-test'):
            self.assertNotIn(f'href="{legacy}"', base)

    def test_profile_saves_country_and_region(self):
        user = self._new_user('region_user')
        response = self.client.post('/profile', data={
            'stage': 'college',
            'stream': 'Commerce',
            'interests_text': 'business and finance',
            'city': 'Mumbai',
            'country': 'India',
            'region': 'Maharashtra',
        })
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            profile = profile_service.get_profile(user['id'])
            self.assertEqual(profile['country'], 'India')
            self.assertEqual(profile['region'], 'Maharashtra')

    def test_legacy_assessment_routes_still_redirect(self):
        self._new_user('legacy_routes_user')
        for path in ('/quiz', '/psychometric-test', '/results',
                     '/psychometric-results', '/iq-test', '/iq-test-results'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/assessment', response.location)


if __name__ == '__main__':
    unittest.main()
