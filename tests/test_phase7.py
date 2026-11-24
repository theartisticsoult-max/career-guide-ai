"""Tests for Phase 7: code-ranked recommendations and LLM explanations."""
import json
import unittest
from unittest.mock import patch

from app import app, db
from app.models import ChosenCareer, Recommendation
from app.services import (
    assessment_service,
    profile_service,
    recommendation_service,
)
from app.services.llm_response import parse_explanation_map
from data.assessment_questions import APTITUDE_QUESTIONS, INTEREST_STATEMENTS


class Phase7TestCase(unittest.TestCase):
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

    def _complete_assessment(self, user, stage='class12', stream='Science',
                             interests='coding algorithms and data'):
        with app.app_context():
            profile_service.save_profile(user['id'], stage, stream, interests, 'Pune')
            state = assessment_service.get_state(user['id'])
            assessment_id = state['assessment_id']
            part1 = {q['id']: 4 for q in INTEREST_STATEMENTS}
            part2 = {q['id']: q['correct'] for q in APTITUDE_QUESTIONS}
            part3 = {
                'salary_priority': 'high', 'team_style': 'team',
                'work_setting': 'desk', 'location': 'city',
                'stability': 'stable', 'study_years': '3-5',
            }
            assessment_service.save_part(user['id'], assessment_id, 1, part1)
            assessment_service.save_part(user['id'], assessment_id, 2, part2)
            assessment_service.save_part(user['id'], assessment_id, 3, part3)
            combined = assessment_service.get_answers(user['id'], assessment_id)
            assessment_service.complete(user['id'], assessment_id, combined)
        return assessment_id


class TestExplanationValidation(Phase7TestCase):
    def test_explanation_map_requires_every_key(self):
        self.assertIsNone(parse_explanation_map('{"C001": "good"}', ['C001', 'C002']))

    def test_explanation_map_ignores_input_order(self):
        raw = '{"C002": "second", "C001": "first"}'
        self.assertEqual(
            parse_explanation_map(raw, ['C001', 'C002']),
            {'C001': 'first', 'C002': 'second'},
        )

    def test_explanation_map_rejects_bad_or_oversized_values(self):
        self.assertIsNone(parse_explanation_map('{"C001": 5}', ['C001']))
        self.assertIsNone(parse_explanation_map(
            json.dumps({'C001': 'x' * 900}), ['C001']
        ))
        self.assertIsNone(parse_explanation_map('{oops', ['C001']))


class TestRanking(Phase7TestCase):
    def test_rank_never_calls_the_llm(self):
        user = self._new_user('rankuser')
        self._complete_assessment(user)
        with app.app_context():
            context = recommendation_service.build_context(user['id'])
            self.assertIsNotNone(context)
            with patch(
                'app.services.chatbot_service.call_groq_completion',
                side_effect=AssertionError('LLM must not be used for ranking'),
            ):
                ranked = recommendation_service.rank(context)
            self.assertEqual(len(ranked), 10)
            self.assertEqual([item['rank'] for item in ranked], list(range(1, 11)))
            scores = [item['score'] for item in ranked]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_profile_stage_filters_careers(self):
        user = self._new_user('stageuser')
        self._complete_assessment(user, stage='class10')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            result = recommendation_service.get_recommendations(user['id'])
        self.assertFalse(result['needs_assessment'])
        self.assertTrue(result['items'])
        for item in result['items']:
            with self.subTest(career_id=item['career_id']):
                self.assertIn('class10', item['stages'].split('|'))


class TestRecommendationsFlow(Phase7TestCase):
    def test_recommendations_require_assessment(self):
        self._new_user('noassessuser')
        response = self.client.get('/recommendations')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/discovery', response.location)

    def test_generate_persist_and_render_recommendations(self):
        user = self._new_user('recflowuser')
        self._complete_assessment(user)
        response = self.client.get('/recommendations')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        self.assertIn('Your Career Matches', html)
        self.assertIn('recommendation-card', html)
        self.assertIn('This career', html)

        with app.app_context():
            assessment = recommendation_service.get_latest_assessment(user['id'])
            rows = Recommendation.query.filter_by(assessment_id=assessment.id).all()
            self.assertEqual(len(rows), 10)
            self.assertEqual([row.rank for row in sorted(rows, key=lambda r: r.rank)], list(range(1, 11)))
            for row in rows:
                self.assertTrue(row.why_fits)
                self.assertGreaterEqual(row.score, 0.0)
                self.assertLessEqual(row.score, 100.0)

    def test_valid_llm_json_replaces_text_without_reordering(self):
        user = self._new_user('llmuser')
        assessment_id = self._complete_assessment(user)
        with app.app_context():
            context = recommendation_service.build_context(user['id'])
            ranked = recommendation_service.rank(context)
            ids = [item['career_id'] for item in ranked]
            explanations = {
                cid: f'Explanation for {cid}' for cid in reversed(ids)
            }
            explanations['NOT_A_CAREER'] = 'extra key is ignored'
            with patch(
                'app.services.chatbot_service.call_groq_completion',
                return_value=json.dumps(explanations),
            ):
                explained = recommendation_service.explain(ranked)
                recommendation_service.save(assessment_id, explained)

            rows = Recommendation.query.filter_by(assessment_id=assessment_id).order_by(
                Recommendation.rank
            ).all()
            self.assertEqual([row.career_id for row in rows], ids)
            for row in rows:
                self.assertEqual(row.why_fits, f'Explanation for {row.career_id}')

    def test_invalid_llm_reply_keeps_fallback_text(self):
        user = self._new_user('fallbackuser')
        self._complete_assessment(user)
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value='{not valid json',
        ):
            result = recommendation_service.get_recommendations(user['id'])
        self.assertTrue(result['items'])
        for item in result['items']:
            self.assertTrue(item['why_fits'].startswith('This career'))

    def test_choose_career_validates_and_persists(self):
        user = self._new_user('chooseuser')
        self._complete_assessment(user)

        bad = self.client.post('/recommendations/choose', data={'career_id': 'NOPE'})
        self.assertEqual(bad.status_code, 302)
        with app.app_context():
            self.assertEqual(ChosenCareer.query.filter_by(user_id=user['id']).count(), 0)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion', return_value=None
        ):
            first_id = recommendation_service.get_recommendations(user['id'])['items'][0]['career_id']

        response = self.client.post('/recommendations/choose', data={'career_id': first_id})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            rows = ChosenCareer.query.filter_by(user_id=user['id']).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].career_id, first_id)

        html = self.client.get('/recommendations').data.decode('utf-8', 'replace')
        self.assertIn('Your chosen career', html)


if __name__ == '__main__':
    unittest.main()
