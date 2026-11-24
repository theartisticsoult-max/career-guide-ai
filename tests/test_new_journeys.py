"""Tests for the DISCOVER -> EXPLORE -> CHOOSE -> GROW entry points."""
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from app import app, db
from app.services import (
    career_data,
    chat_service,
    chatbot_service,
    discovery_service,
    profile_service,
    recommendation_service,
    roadmap_service,
)

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

    def _discovery_form(self):
        return MultiDict([
            ('d1', 'working'),
            ('d2', 'Arts'),
            ('d3', 'A'),
            ('d3', 'S'),
            ('d4', 'english'),
            ('d5', 'words'),
            ('d6', 'mixed'),
            ('d7', 'team'),
            ('d8', 'stable'),
            ('d9', '3-5'),
            ('d10', 'low'),
            ('d11', 'town'),
            ('d12', 'yes'),
        ])

    def test_discovery_page_has_twelve_questions_without_scores(self):
        self._new_user('discovery_page_user')
        response = self.client.get('/discovery')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        self.assertIn('12 questions', html)
        self.assertIn('not an IQ test', html)
        self.assertEqual(len(re.findall(r'<label>\d+\.', html)), 12)
        self.assertIn('name="d1"', html)
        self.assertIn('name="d12"', html)
        self.assertNotIn("'riasec'", html)

    def test_discovery_completion_feeds_recommendations(self):
        user = self._new_user('discovery_flow_user')
        response = self.client.post('/discovery', data=self._discovery_form())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/recommendations', response.location)

        with app.app_context():
            state = discovery_service.get_state(user['id'])
            self.assertEqual(state['status'], 'completed')
            self.assertEqual(len(state['saved']), 12)
            profile = profile_service.get_profile(user['id'])
            self.assertEqual(profile['stage'], 'college')
            self.assertEqual(profile['stream'], 'Arts')
            result = recommendation_service.get_recommendations(user['id'])
            self.assertFalse(result['needs_assessment'])
            self.assertEqual(len(result['items']), 10)
            self.assertTrue(any(item['non_tech_eligible'] for item in result['items']))
            for item in result['items']:
                self.assertTrue(item['licensing_note'])
                self.assertTrue(item['pathway'])

        html = self.client.get('/recommendations').data.decode('utf-8', 'replace')
        self.assertIn('Your Career Matches', html)
        self.assertIn('Top 3 to explore first', html)
        self.assertIn('More careers to explore', html)
        self.assertIn('Strengths to build on', html)
        self.assertIn('Possible pathway', html)
        self.assertNotIn('% match', html)

    def test_discovery_rejects_incomplete_answers(self):
        user = self._new_user('discovery_invalid_user')
        form = self._discovery_form()
        form.pop('d9')
        response = self.client.post('/discovery', data=form)
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            state = discovery_service.get_state(user['id'])
            self.assertEqual(state['status'], 'in_progress')
            self.assertEqual(state['saved'], {})

    def test_dataset_exposes_location_and_eligibility_metadata(self):
        with app.app_context():
            career = career_data.get_career('C001')
            for field in ('country', 'region', 'eligible_streams',
                          'non_tech_eligible', 'licensing_note', 'pathway'):
                self.assertIn(field, career)
                self.assertTrue(str(career[field]).strip())

    def test_chat_context_includes_location_without_inventing_scores(self):
        user = self._new_user('mentor_context_user')
        with app.app_context():
            profile_service.save_profile(
                user['id'], 'college', 'Arts', 'design',
                city='Pune', country='India', region='Maharashtra',
            )
            context = chat_service.build_context(user['id'])
            self.assertIn('Country: India', context)
            self.assertIn('State/region: Maharashtra', context)
            self.assertNotIn('% match', context)

    def test_roadmap_is_actionable_and_can_change_career(self):
        user = self._new_user('roadmap_journey_user')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            careers = career_data.get_all_careers()
            first = next(c for c in careers if c['Category'] == 'Healthcare')
            second = next(c for c in careers if c['Category'] == 'Arts')

            recommendation_service.choose_career_direct(user['id'], first['Career_ID'])
            roadmap = roadmap_service.get_roadmap(user['id'])
            self.assertEqual(len(roadmap['items']), 6)
            phases = ' '.join(item['phase'] for item in roadmap['items'])
            self.assertIn('Weeks', phases)
            self.assertIn('Month', phases)
            details = ' '.join(item['detail'] for item in roadmap['items']).lower()
            for expected in ('portfolio', 'internship', 'resume', 'interview',
                             'certification', 'resources'):
                self.assertIn(expected, details)
            self.assertTrue(roadmap['next_milestone'])

            first_item = roadmap['items'][0]['id']
            roadmap_service.toggle_item(user['id'], first_item)
            resumed = roadmap_service.get_roadmap(user['id'])
            self.assertEqual(resumed['done_count'], 1)
            self.assertNotEqual(resumed['next_milestone']['id'], first_item)

            recommendation_service.choose_career_direct(user['id'], second['Career_ID'])
            changed = roadmap_service.get_roadmap(user['id'])
            self.assertEqual(changed['career']['career_id'], second['Career_ID'])
            self.assertNotEqual(changed['roadmap_id'], roadmap['roadmap_id'])
            self.assertEqual(changed['progress'], 0)

        with patch('app.services.chatbot_service.call_groq_completion', return_value=None):
            html = self.client.get('/roadmap').data.decode('utf-8', 'replace')
        self.assertIn('Career overview', html)
        self.assertIn('Change career', html)
        self.assertIn('Resume with', html)
        self.assertIn('Learning Resources', html)

    def test_mentor_uses_saved_context_and_validates_llm_json(self):
        user = self._new_user('mentor_full_context_user')
        self.client.post('/discovery', data=self._discovery_form())
        with app.app_context():
            profile_service.save_profile(
                user['id'], 'college', 'Arts', 'design and community work',
                city='Pune', country='India', region='Maharashtra',
            )
            items = recommendation_service.get_recommendations(user['id'])['items']
            recommendation_service.choose_career_direct(user['id'], items[0]['career_id'])
            roadmap = roadmap_service.get_roadmap(user['id'])
            roadmap_service.toggle_item(user['id'], roadmap['items'][0]['id'])
            context = chat_service.build_context(user['id'])

        for expected in (
            'Learning goals stated', 'Discovery answers', 'Careers to explore',
            'Chosen career', 'Completed milestones', 'Next milestone',
            'Country: India', 'State/region: Maharashtra',
        ):
            self.assertIn(expected, context)
        self.assertNotIn('% match', context)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value='unstructured plain text',
        ):
            fallback = chat_service.respond(user['id'], 'What should I do next?')
        self.assertIn('**What I know**', fallback)
        self.assertIn('**Practical next steps**', fallback)
        self.assertIn('**Clarifying question**', fallback)
        self.assertNotIn('unstructured plain text', fallback)
        self.assertNotIn('LPA', fallback)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=json.dumps({'answer': '**Valid** mentor answer'}),
        ):
            valid = chat_service.respond(user['id'], 'What next?')
        self.assertEqual(valid, '**Valid** mentor answer')
        self.assertNotIn('salary expectations', chatbot_service.SYSTEM_PROMPT.lower())


if __name__ == '__main__':
    unittest.main()
