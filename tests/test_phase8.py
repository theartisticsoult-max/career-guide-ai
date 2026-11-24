"""Tests for Phase 8: roadmap generation and progress tracking."""
import json
import unittest
from unittest.mock import patch

from app import app, db
from app.models import Roadmap, RoadmapItem
from app.services import assessment_service, profile_service, recommendation_service, roadmap_service
from app.services.llm_response import parse_roadmap
from data.assessment_questions import APTITUDE_QUESTIONS, INTEREST_STATEMENTS


ROADMAP_JSON = {
    'roadmap': [
        {'phase': 'Start', 'type': 'skill', 'title': 'LLM Step One',
         'detail': 'Learn the basics.', 'est_weeks': 2},
        {'phase': 'Build', 'type': 'project', 'title': 'LLM Step Two',
         'detail': 'Build a small project.', 'est_weeks': 4},
        {'phase': 'Apply', 'type': 'exam', 'title': 'LLM Step Three',
         'detail': 'Prepare for entry requirements.', 'est_weeks': 3},
    ]
}


class Phase8TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

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

    def _choose_career(self, user):
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            items = recommendation_service.get_recommendations(user['id'])['items']
            career_id = items[0]['career_id']
            recommendation_service.choose_career(user['id'], career_id)
        return career_id

    def _prepare_user(self, username):
        user = self._new_user(username)
        with app.app_context():
            profile_service.save_profile(user['id'], 'class12', 'Science', 'coding', 'Pune')
            state = assessment_service.get_state(user['id'])
            assessment_id = state['assessment_id']
            answers = {q['id']: 4 for q in INTEREST_STATEMENTS}
            answers.update({q['id']: q['correct'] for q in APTITUDE_QUESTIONS})
            assessment_service.save_part(user['id'], assessment_id, 1, answers)
            assessment_service.save_part(user['id'], assessment_id, 2, answers)
            assessment_service.save_part(user['id'], assessment_id, 3, {
                'salary_priority': 'high', 'team_style': 'team',
                'work_setting': 'desk', 'location': 'city',
                'stability': 'stable', 'study_years': '3-5',
            })
            combined = assessment_service.get_answers(user['id'], assessment_id)
            assessment_service.complete(user['id'], assessment_id, combined)
        self._choose_career(user)
        return user


class TestRoadmapValidation(Phase8TestCase):
    def test_valid_roadmap_is_accepted(self):
        parsed = parse_roadmap(json.dumps(ROADMAP_JSON))
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]['title'], 'LLM Step One')

    def test_invalid_types_and_ranges_are_rejected(self):
        bad = json.loads(json.dumps(ROADMAP_JSON))
        bad['roadmap'][1]['type'] = 'unknown'
        self.assertIsNone(parse_roadmap(json.dumps(bad)))

        bad = json.loads(json.dumps(ROADMAP_JSON))
        bad['roadmap'][0]['est_weeks'] = 999
        self.assertIsNone(parse_roadmap(json.dumps(bad)))

        self.assertIsNone(parse_roadmap('{not json'))
        self.assertIsNone(parse_roadmap(json.dumps({'roadmap': [ROADMAP_JSON['roadmap'][0]]})))


class TestRoadmapFlow(Phase8TestCase):
    def test_roadmap_requires_chosen_career(self):
        self._new_user('nocareeruser')
        response = self.client.get('/roadmap')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/recommendations', response.location)

    def test_fallback_roadmap_is_generated_and_persisted(self):
        user = self._prepare_user('fallbackroaduser')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            result = roadmap_service.get_roadmap(user['id'])

        self.assertFalse(result['needs_career'])
        self.assertEqual(result['progress'], 0)
        self.assertEqual(len(result['items']), 6)
        allowed = {'skill', 'course', 'project', 'certification', 'exam'}
        for item in result['items']:
            self.assertIn(item['type'], allowed)
            self.assertTrue(item['title'])
            self.assertFalse(item['done'])

        with app.app_context():
            self.assertEqual(Roadmap.query.filter_by(user_id=user['id']).count(), 1)
            self.assertEqual(RoadmapItem.query.join(Roadmap).filter(
                Roadmap.user_id == user['id']
            ).count(), 6)

    def test_valid_llm_roadmap_is_used(self):
        user = self._prepare_user('llmroaduser')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=json.dumps(ROADMAP_JSON),
        ):
            result = roadmap_service.get_roadmap(user['id'])
        self.assertEqual(len(result['items']), 3)
        self.assertEqual(result['items'][0]['title'], 'LLM Step One')

    def test_invalid_llm_roadmap_uses_fallback(self):
        user = self._prepare_user('badroaduser')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value='{invalid',
        ):
            result = roadmap_service.get_roadmap(user['id'])
        self.assertEqual(len(result['items']), 6)
        self.assertTrue(result['items'][0]['title'])

    def test_progress_toggle_updates_state(self):
        user = self._prepare_user('progressuser')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            result = roadmap_service.get_roadmap(user['id'])
        item_id = result['items'][0]['id']

        response = self.client.post('/roadmap', data={'item_id': item_id})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            item = RoadmapItem.query.get(item_id)
            self.assertTrue(item.done)
            self.assertIsNotNone(item.done_at)

        with app.app_context():
            result = roadmap_service.get_roadmap(user['id'])
        self.assertEqual(result['done_count'], 1)
        self.assertEqual(result['progress'], 17)

        self.client.post('/roadmap', data={'item_id': item_id})
        with app.app_context():
            item = RoadmapItem.query.get(item_id)
            self.assertFalse(item.done)
            self.assertIsNone(item.done_at)

    def test_invalid_item_id_is_rejected(self):
        user = self._prepare_user('baditemuser')
        self.client.post('/roadmap', data={'item_id': 'not-a-number'})
        with app.app_context():
            self.assertEqual(roadmap_service.get_roadmap(user['id'])['progress'], 0)

    def test_roadmap_page_renders_progress_and_items(self):
        self._prepare_user('roadpageuser')
        with patch('app.services.chatbot_service.call_groq_completion', return_value=None):
            response = self.client.get('/roadmap')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        self.assertIn('Your Career Roadmap', html)
        self.assertIn('progress-bar', html)
        self.assertIn('Mark as done', html)


if __name__ == '__main__':
    unittest.main()
