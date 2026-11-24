"""Tests for Phase 6: combined assessment and server-side scoring."""
import json
import unittest

from app import app, db
from app.extensions import sqlalchemy
from app.models import Assessment, AssessmentAnswer, AssessmentScore
from app.services import assessment_service, scoring
from data.assessment_questions import (
    APTITUDE_QUESTIONS,
    INTEREST_STATEMENTS,
    PREFERENCE_QUESTIONS,
    RIASEC_TYPES,
)


class Phase6TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _new_user(self, username='assessmentuser'):
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


class TestScoring(Phase6TestCase):
    def test_interest_scoring_fixed_inputs(self):
        high = scoring.score_interests({q['id']: 5 for q in INTEREST_STATEMENTS})
        self.assertEqual(high, {letter: 1.0 for letter in RIASEC_TYPES})
        low = scoring.score_interests({q['id']: 1 for q in INTEREST_STATEMENTS})
        self.assertEqual(low, {letter: 0.2 for letter in RIASEC_TYPES})

    def test_aptitude_grading_is_server_side(self):
        correct = scoring.score_aptitude({q['id']: q['correct'] for q in APTITUDE_QUESTIONS})
        self.assertEqual(correct['correct_count'], 12)
        for section in ('numerical', 'verbal', 'logical', 'spatial'):
            self.assertEqual(correct[section], 1.0)

        wrong = scoring.score_aptitude({q['id']: 3 for q in APTITUDE_QUESTIONS})
        self.assertEqual(wrong['correct_count'], 0)

    def test_preferences_and_payload(self):
        prefs = scoring.score_preferences({
            'salary_priority': 'high', 'team_style': 'solo', 'work_setting': 'field',
            'location': 'remote', 'stability': 'risk', 'study_years': '6+',
        })
        self.assertEqual(prefs, {
            'salary_priority': 1.0, 'team_style': 0.0, 'work_setting': 1.0,
            'location': 1.0, 'stability': 0.0, 'study_years': 1.0,
        })
        answers = {q['id']: 5 for q in INTEREST_STATEMENTS}
        answers.update({q['id']: q['correct'] for q in APTITUDE_QUESTIONS})
        payload = scoring.build_score_payload(answers)
        self.assertEqual(payload['top_riasec'], scoring.top_riasec(payload['riasec']))
        self.assertEqual(json.loads(payload['riasec_json'])['R'], 1.0)
        self.assertEqual(json.loads(payload['aptitude_json'])['numerical'], 1.0)

    def test_client_questions_never_include_answers(self):
        questions = assessment_service.questions_for_part(2)
        self.assertEqual(len(questions), 12)
        for question in questions:
            self.assertNotIn('correct', question)


class TestAssessmentFlow(Phase6TestCase):
    def test_legacy_routes_redirect_to_combined_assessment(self):
        self._new_user()
        for path in ('/quiz', '/psychometric-test', '/iq-test', '/results',
                     '/psychometric-results', '/iq-test-results'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/assessment', response.location)

    def test_three_parts_save_resume_and_complete(self):
        user = self._new_user('flowuser')
        response = self.client.get('/assessment')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8', 'replace')
        self.assertIn('Part 1 of 3', html)
        self.assertIn('quiz-progress', html)

        part1 = {q['id']: 4 for q in INTEREST_STATEMENTS}
        response = self.client.post('/assessment', data=dict(part=1, **part1))
        self.assertEqual(response.status_code, 302)
        self.assertIn('part=2', response.location)

        with app.app_context():
            state = assessment_service.get_state(user['id'])
            self.assertEqual(state['current_part'], 2)

        response = self.client.get('/assessment?part=1')
        self.assertRegex(
            response.data.decode('utf-8', 'replace'),
            r'name="I1" value="4"[^>]*checked',
        )

        part2 = {q['id']: q['correct'] for q in APTITUDE_QUESTIONS}
        response = self.client.post('/assessment', data=dict(part=2, **part2))
        self.assertEqual(response.status_code, 302)
        self.assertIn('part=3', response.location)

        part3 = {q['id']: q['options'][0]['value'] for q in PREFERENCE_QUESTIONS}
        response = self.client.post('/assessment', data=dict(part=3, **part3))
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            assessment = Assessment.query.filter_by(user_id=user['id']).first()
            self.assertEqual(assessment.status, 'completed')
            self.assertIsNotNone(assessment.finished_at)
            score = AssessmentScore.query.filter_by(assessment_id=assessment.id).first()
            self.assertIsNotNone(score)
            self.assertEqual(json.loads(score.riasec_json)['R'], 0.8)
            self.assertEqual(json.loads(score.aptitude_json)['numerical'], 1.0)
            answers = AssessmentAnswer.query.filter_by(assessment_id=assessment.id).count()
            self.assertEqual(answers, 3)

    def test_assessment_route_introduces_aptitude_terminology(self):
        user = self._new_user('aptitudeuser')
        with app.app_context():
            state = assessment_service.get_state(user['id'])
            assessment_service.save_part(user['id'], state['assessment_id'], 1, {})
        html = self.client.get('/assessment?part=2').data.decode('utf-8', 'replace')
        self.assertIn('Aptitude', html)
        self.assertIn('not a clinical test', html)
        self.assertNotIn('IQ Test', html)


if __name__ == '__main__':
    unittest.main()
