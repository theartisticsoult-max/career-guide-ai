"""Tests for Phase 9: context-aware chatbot with stored history."""
import json
import unittest
from unittest.mock import patch

from app import app, db
from app.models import ChosenCareer, ChatMessage, Roadmap, RoadmapItem
from app.services import career_data, chat_service, profile_service
from app.extensions import sqlalchemy


GOOD_LLM_REPLY = json.dumps({'answer': 'Context-aware answer'})


class Phase9TestCase(unittest.TestCase):
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

    def _setup_context(self, user):
        with app.app_context():
            profile_service.save_profile(
                user['id'], 'class12', 'Science', 'coding and data', 'Pune'
            )
            sqlalchemy.session.add(ChosenCareer(user_id=user['id'], career_id='C001'))
            roadmap = Roadmap(user_id=user['id'], career_id='C001', version=1)
            sqlalchemy.session.add(roadmap)
            sqlalchemy.session.flush()
            sqlalchemy.session.add(RoadmapItem(
                roadmap_id=roadmap.id, phase='Phase 1', type='skill',
                title='Learn basics', est_weeks=2, done=True,
            ))
            sqlalchemy.session.add(RoadmapItem(
                roadmap_id=roadmap.id, phase='Phase 1', type='course',
                title='Take course', est_weeks=4, done=False,
            ))
            sqlalchemy.session.commit()
        return career_data.get_career('C001')


class TestChatContext(Phase9TestCase):
    def test_context_contains_profile_career_and_progress(self):
        user = self._new_user('ctxuser')
        career = self._setup_context(user)
        with app.app_context():
            context = chat_service.build_context(user['id'])
        self.assertIn('class12', context)
        self.assertIn('Science', context)
        self.assertIn('Pune', context)
        self.assertIn(career['Career_Name'], context)
        self.assertIn('1 of 2 steps done', context)

    def test_logged_in_history_ignores_client_history(self):
        user = self._new_user('historyuser')
        self._setup_context(user)
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=GOOD_LLM_REPLY,
        ) as mock_call:
            chat_service.respond(user['id'], 'current question', [
                {'role': 'user', 'content': 'CLIENT-ONLY'}
            ])
            args = mock_call.call_args.args
        self.assertNotIn('CLIENT-ONLY', json.dumps(args))
        self.assertIn('class12', args[1])
        self.assertEqual(args[2], [])

    def test_anonymous_uses_client_history_without_context(self):
        with patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=GOOD_LLM_REPLY,
        ) as mock_call:
            answer = chat_service.respond(None, 'current question', [
                {'role': 'user', 'content': 'ANONYMOUS-CONTEXT'}
            ])
            args = mock_call.call_args.args
        self.assertEqual(answer, 'Context-aware answer')
        self.assertEqual(args[2], [{'role': 'user', 'content': 'ANONYMOUS-CONTEXT'}])
        self.assertNotIn('Known user context', args[1])

    def test_prompt_history_keeps_last_eight_turns_in_order(self):
        user = self._new_user('turnuser')
        with app.app_context():
            for index in range(10):
                sqlalchemy.session.add(ChatMessage(
                    user_id=user['id'], role='user', message=f'old {index}'
                ))
            sqlalchemy.session.commit()
            history = chat_service.get_prompt_history(user['id'])
        self.assertEqual([turn['content'] for turn in history],
                         [f'old {index}' for index in range(2, 10)])


class TestChatPersistence(Phase9TestCase):
    def test_response_is_saved_for_logged_in_users(self):
        user = self._new_user('saveuser')
        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=GOOD_LLM_REPLY,
        ):
            answer = chat_service.respond(user['id'], 'Tell me about my roadmap')
        self.assertEqual(answer, 'Context-aware answer')
        with app.app_context():
            rows = ChatMessage.query.filter_by(user_id=user['id']).order_by(
                ChatMessage.id
            ).all()
        self.assertEqual([row.role for row in rows], ['user', 'assistant'])
        self.assertEqual(rows[0].message, 'Tell me about my roadmap')
        self.assertEqual(rows[1].message, 'Context-aware answer')

    def test_history_and_clear_endpoints(self):
        user = self._new_user('endpointuser')
        with app.app_context():
            sqlalchemy.session.add(ChatMessage(
                user_id=user['id'], role='user', message='saved question'
            ))
            sqlalchemy.session.commit()

        history = self.client.get('/api/chatbot/history').json
        self.assertTrue(history['logged_in'])
        self.assertEqual([m['message'] for m in history['messages']], ['saved question'])

        cleared = self.client.post('/api/chatbot/clear')
        self.assertEqual(cleared.status_code, 200)
        self.assertTrue(cleared.json['success'])
        self.assertEqual(self.client.get('/api/chatbot/history').json['messages'], [])

    def test_api_chatbot_persists_for_logged_in_user(self):
        user = self._new_user('apiusersave')
        with patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=GOOD_LLM_REPLY,
        ):
            response = self.client.post('/api/chatbot', json={'message': 'Hello there'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['response'], 'Context-aware answer')
        with app.app_context():
            self.assertEqual(ChatMessage.query.filter_by(user_id=user['id']).count(), 2)

    def test_anonymous_history_endpoint_has_no_messages(self):
        result = self.client.get('/api/chatbot/history').json
        self.assertFalse(result['logged_in'])
        self.assertEqual(result['messages'], [])


if __name__ == '__main__':
    unittest.main()
