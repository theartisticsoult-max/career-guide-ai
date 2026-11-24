"""Tests for Phase 4: new tables and the one-time profile screen."""
import os
import unittest
from pathlib import Path

from sqlalchemy import inspect

from app import app, db
from app.extensions import sqlalchemy as sa_extension
from app.services import profile_service

ROOT = Path(__file__).resolve().parents[1]


class Phase4TestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _new_user(self, username='profileuser'):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        created = db.create_user(username, f'{username}@example.com', 'password123')
        self.assertTrue(created['success'])
        return db.get_user_by_username(username)

    def _login(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['username'] = 'profileuser'
            session['is_admin'] = 0


class TestNewTables(Phase4TestCase):
    def test_all_phase4_tables_exist(self):
        with app.app_context():
            inspector = inspect(sa_extension.engine)
        for table in (
            'profiles', 'assessments', 'assessment_answers', 'assessment_scores',
            'recommendations', 'chosen_careers', 'roadmaps', 'roadmap_items',
            'chat_messages',
        ):
            with self.subTest(table=table):
                self.assertTrue(inspector.has_table(table))

    def test_new_tables_cascade_on_user_delete(self):
        user = self._new_user('cascade4user')
        user_id = user['id']
        with app.app_context():
            profile_service.save_profile(user_id, 'class12', 'Science', 'coding', 'Pune')
            from app.models import Assessment, AssessmentAnswer, AssessmentScore, ChatMessage
            from app.models import ChosenCareer, Recommendation, Roadmap, RoadmapItem
            from app.extensions import sqlalchemy

            assessment = Assessment(user_id=user_id, status='in_progress', current_part=1)
            sqlalchemy.session.add(assessment)
            sqlalchemy.session.flush()
            sqlalchemy.session.add(AssessmentAnswer(
                assessment_id=assessment.id, part=1, question_key='q1', answer_text='5'
            ))
            sqlalchemy.session.add(AssessmentScore(
                assessment_id=assessment.id, riasec_json='{}', aptitude_json='{}', prefs_json='{}'
            ))
            sqlalchemy.session.add(Recommendation(
                assessment_id=assessment.id, career_id='C001', rank=1, score=90.0, why_fits='test'
            ))
            sqlalchemy.session.add(ChosenCareer(user_id=user_id, career_id='C001'))
            roadmap = Roadmap(user_id=user_id, career_id='C001', version=1)
            sqlalchemy.session.add(roadmap)
            sqlalchemy.session.flush()
            sqlalchemy.session.add(RoadmapItem(
                roadmap_id=roadmap.id, phase='Phase 1', type='skill', title='Learn Python',
                detail='Basics', est_weeks=4, done=False,
            ))
            sqlalchemy.session.add(ChatMessage(
                user_id=user_id, role='user', message='hello'
            ))
            sqlalchemy.session.commit()
            assessment_id = assessment.id
            roadmap_id = roadmap.id

        db.delete_user(user_id)
        conn = db.get_connection()
        checks = (
            ('profiles', 'user_id', user_id),
            ('assessments', 'user_id', user_id),
            ('assessment_answers', 'assessment_id', assessment_id),
            ('assessment_scores', 'assessment_id', assessment_id),
            ('recommendations', 'assessment_id', assessment_id),
            ('chosen_careers', 'user_id', user_id),
            ('roadmaps', 'user_id', user_id),
            ('roadmap_items', 'roadmap_id', roadmap_id),
            ('chat_messages', 'user_id', user_id),
        )
        for table, column, value in checks:
            with self.subTest(table=table):
                self.assertEqual(
                    conn.execute(f'SELECT COUNT(*) FROM {table} WHERE {column} = ?', (value,)).fetchone()[0],
                    0,
                )
        conn.close()


class TestProfileFlow(Phase4TestCase):
    def test_registration_redirects_to_profile(self):
        response = self.client.post('/register', data={
            'username': 'newprofileuser',
            'email': 'newprofileuser@example.com',
            'password': 'password123',
            'full_name': 'New User',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('/profile', response.location)

    def test_profile_form_save_and_one_time_prompt(self):
        user = self._new_user('profileflowuser')
        self._login(user['id'])

        dashboard = self.client.get('/dashboard').data.decode('utf-8', 'replace')
        self.assertIn('Fill in your profile', dashboard)

        response = self.client.post('/profile', data={
            'stage': 'class12',
            'stream': 'Commerce',
            'interests_text': 'marketing and finance',
            'city': 'Mumbai',
        })
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            profile = profile_service.get_profile(user['id'])
        self.assertEqual(profile['stage'], 'class12')
        self.assertEqual(profile['stream'], 'Commerce')
        self.assertEqual(profile['city'], 'Mumbai')

        dashboard = self.client.get('/dashboard').data.decode('utf-8', 'replace')
        self.assertNotIn('Fill in your profile', dashboard)

    def test_invalid_stage_is_rejected(self):
        user = self._new_user('badstageuser')
        self._login(user['id'])
        response = self.client.post('/profile', data={'stage': 'class11'})
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertTrue(profile_service.needs_profile(user['id']))

    def test_profile_service_updates_existing_profile(self):
        user = self._new_user('updateprofileuser')
        with app.app_context():
            first = profile_service.save_profile(user['id'], 'class10', 'Science')
            self.assertTrue(first['success'])
            second = profile_service.save_profile(user['id'], 'college', 'Engineering', 'AI', 'Delhi')
            self.assertTrue(second['success'])
            profile = profile_service.get_profile(user['id'])
            self.assertEqual(profile['stage'], 'college')
            self.assertEqual(profile['city'], 'Delhi')
            self.assertFalse(profile_service.needs_profile(user['id']))


class TestMigration(Phase4TestCase):
    def test_phase4_migration_revision_exists(self):
        versions = list((ROOT / 'migrations' / 'versions').glob('*.py'))
        self.assertEqual(len(versions), 2)
        contents = ''.join(path.read_text(encoding='utf-8') for path in versions)
        for table in ('profiles', 'assessments', 'roadmap_items', 'chat_messages'):
            self.assertIn(f"'{table}'", contents)


if __name__ == '__main__':
    unittest.main()
