"""Tests for AI Career Mentor short follow-ups and provider-failure fallbacks."""
import json
import unittest
from unittest.mock import MagicMock, patch

from app import app, db
from app.extensions import sqlalchemy
from app.models import ChatMessage
from app.services import (
    chat_service,
    profile_service,
    recommendation_service,
    roadmap_service,
)

CLARIFICATION = (
    'Which part do you want help with next: '
    'qualifications, skills, projects or applications?'
)
PROVIDER_CLARIFICATION = json.dumps({'answer': CLARIFICATION})


class MentorFollowupTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _new_user(self, username):
        conn = db.get_connection()
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        conn.commit()
        conn.close()
        created = db.create_user(
            username, f'{username}@example.com', 'password123'
        )
        self.assertTrue(created['success'])
        user = db.get_user_by_username(username)
        with self.client.session_transaction() as session:
            session['user_id'] = user['id']
            session['username'] = username
            session['is_admin'] = 0
        return user

    def _setup_mentor(self, user, career_id='C074'):
        with app.app_context():
            profile_service.save_profile(
                user['id'], 'college', 'Any', 'business',
                city='Pune', country='India', region='Maharashtra',
            )
            recommendation_service.choose_career_direct(user['id'], career_id)
            roadmap_service.get_roadmap(user['id'])
            sqlalchemy.session.add_all([
                ChatMessage(
                    user_id=user['id'], role='user',
                    message='What should I learn next for my roadmap?',
                ),
                ChatMessage(
                    user_id=user['id'], role='assistant',
                    message=CLARIFICATION,
                ),
            ])
            sqlalchemy.session.commit()

    def _messages(self, user_id):
        with app.app_context():
            return [
                row.message for row in ChatMessage.query.filter_by(
                    user_id=user_id
                ).order_by(ChatMessage.id).all()
            ]

    def test_skills_followup_uses_saved_career_and_answers_directly(self):
        user = self._new_user('mentor_skills_followup')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=PROVIDER_CLARIFICATION,
        ) as provider:
            response = chat_service.respond(user['id'], 'skills')

        lowered = response.lower()
        for expected in (
            'communication', 'leadership', 'business fundamentals',
            'marketing', 'financial literacy', 'problem-solving',
            'practical learning order', 'beginner-friendly exercise',
            'entrepreneur', 'pune, maharashtra, india',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, lowered)
        self.assertNotIn('**what i know**', lowered)
        self.assertNotIn('which part do you want help with', lowered)
        provider.assert_not_called()

        messages = self._messages(user['id'])
        self.assertEqual(messages[-2], 'skills')
        self.assertEqual(messages[-1], response)
        self.assertEqual(messages.count(CLARIFICATION), 1)

    def test_projects_followup_suggests_beginner_projects(self):
        user = self._new_user('mentor_projects_followup')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=PROVIDER_CLARIFICATION,
        ) as provider:
            response = chat_service.respond(user['id'], 'projects')

        lowered = response.lower()
        for expected in (
            'small business plan', 'customer survey',
            'simple budget spreadsheet', 'marketing campaign', 'teaches',
            'entrepreneur',
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, lowered)
        self.assertNotIn('which part do you want help with', lowered)
        self.assertNotIn('**what i know**', lowered)
        provider.assert_not_called()

        messages = self._messages(user['id'])
        self.assertEqual(messages[-2], 'projects')
        self.assertEqual(messages[-1], response)

    def test_qualifications_and_applications_followups_are_context_aware(self):
        user = self._new_user('mentor_requirements_followup')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=PROVIDER_CLARIFICATION,
        ):
            qualifications = chat_service.respond(user['id'], 'qualifications')
            applications = chat_service.respond(user['id'], 'applications')

        qualifications_lower = qualifications.lower()
        self.assertIn('educational pathway and requirements', qualifications_lower)
        self.assertIn('any degree', qualifications_lower)
        self.assertIn('no fixed entrance exam', qualifications_lower)
        self.assertIn('college', qualifications_lower)
        self.assertIn('india', qualifications_lower)
        self.assertNotIn('which part do you want help with', qualifications_lower)

        applications_lower = applications.lower()
        self.assertIn('practical opportunities and how to prepare', applications_lower)
        self.assertIn('one-page', applications_lower)
        self.assertIn('customer', applications_lower)
        self.assertIn('local check', applications_lower)
        self.assertNotIn('which part do you want help with', applications_lower)

        messages = self._messages(user['id'])
        self.assertEqual(messages[-4], 'qualifications')
        self.assertEqual(messages[-3], qualifications)
        self.assertEqual(messages[-2], 'applications')
        self.assertEqual(messages[-1], applications)

    def test_multi_turn_history_follows_latest_message(self):
        user = self._new_user('mentor_multi_turn')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=PROVIDER_CLARIFICATION,
        ) as provider:
            skills = chat_service.respond(user['id'], 'skills')
            projects = chat_service.respond(user['id'], 'projects')
            qualifications = chat_service.respond(user['id'], 'qualifications')

        self.assertNotEqual(skills, projects)
        self.assertNotEqual(projects, qualifications)
        self.assertIn('beginner-friendly projects', projects.lower())
        self.assertIn('educational pathway', qualifications.lower())

        messages = self._messages(user['id'])
        self.assertEqual(len(messages), 8)
        self.assertEqual(
            [message for message in messages if message in
             ('skills', 'projects', 'qualifications')],
            ['skills', 'projects', 'qualifications'],
        )
        self.assertEqual(messages[0], 'What should I learn next for my roadmap?')
        self.assertEqual(messages[-1], qualifications)
        provider.assert_not_called()

    def test_history_is_passed_to_provider_for_non_followup_question(self):
        user = self._new_user('mentor_history_provider')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=json.dumps({'answer': 'Context-aware answer'}),
        ) as provider:
            response = chat_service.respond(
                user['id'], 'What else should I check locally?'
            )

        self.assertEqual(response, 'Context-aware answer')
        provider.assert_called_once()
        args = provider.call_args.args
        self.assertEqual(args[0], 'What else should I check locally?')
        self.assertIn('college', args[1])
        self.assertIn('Entrepreneur', args[1])
        self.assertIn(CLARIFICATION, [turn['content'] for turn in args[2]])

    def test_provider_failure_still_gives_useful_followup_answers(self):
        user = self._new_user('mentor_provider_failure')
        self._setup_mentor(user)

        cases = (
            ('skills', 'practical learning order'),
            ('projects', 'customer survey'),
            ('qualifications', 'educational pathway'),
            ('applications', 'one-page'),
        )
        for message, expected in cases:
            with self.subTest(message=message), app.app_context(), patch(
                'app.services.chatbot_service.call_groq_completion',
                side_effect=RuntimeError('provider unavailable'),
            ) as provider:
                response = chat_service.respond(user['id'], message)
                provider.assert_not_called()
            self.assertIn(expected, response.lower())
            self.assertNotIn('which part do you want help with', response.lower())

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=None,
        ):
            generic = chat_service.respond(user['id'], 'What should I do next?')
        self.assertIn('**practical next steps**', generic.lower())

    def test_provider_error_uses_fallback_and_preserves_history(self):
        user = self._new_user('mentor_provider_error_history')
        self._setup_mentor(user)

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError(
            'provider unavailable'
        )
        with app.app_context(), patch(
            'app.services.chatbot_service.get_groq_client',
            return_value=mock_client,
        ):
            response = chat_service.respond(user['id'], 'What should I do next?')

        self.assertIn('**practical next steps**', response.lower())
        messages = self._messages(user['id'])
        self.assertEqual(messages[-2], 'What should I do next?')
        self.assertEqual(messages[-1], response)

    def test_no_repeated_clarification_loop(self):
        user = self._new_user('mentor_no_loop')
        self._setup_mentor(user)

        with app.app_context(), patch(
            'app.services.chatbot_service.call_groq_completion',
            return_value=PROVIDER_CLARIFICATION,
        ) as provider:
            chat_service.respond(user['id'], 'skills')
            chat_service.respond(user['id'], 'projects')

        assistant_messages = [
            message for message in self._messages(user['id'])
            if message == CLARIFICATION
        ]
        self.assertEqual(len(assistant_messages), 1)
        provider.assert_not_called()

    def test_anonymous_followup_uses_client_history_without_profile_dump(self):
        history = [
            {'role': 'user', 'content': 'What should I learn next?'},
            {'role': 'assistant', 'content': CLARIFICATION},
        ]
        with patch(
            'app.services.chatbot_service.call_groq_completion',
            side_effect=RuntimeError('provider unavailable'),
        ) as provider:
            response = chat_service.respond(None, 'skills', history)

        self.assertIn('practical learning order', response.lower())
        self.assertIn('communication', response.lower())
        self.assertNotIn('known user context', response.lower())
        provider.assert_not_called()

    def test_api_chatbot_returns_followup_and_persists_for_logged_in_user(self):
        user = self._new_user('mentor_api_followup')
        self._setup_mentor(user)

        with patch(
            'app.services.chatbot_service.call_groq_completion',
            side_effect=RuntimeError('provider unavailable'),
        ) as provider:
            result = self.client.post('/api/chatbot', json={'message': 'skills'})

        self.assertEqual(result.status_code, 200)
        self.assertIn('practical learning order', result.json['response'].lower())
        provider.assert_not_called()

        messages = self._messages(user['id'])
        self.assertEqual(messages[-2], 'skills')
        self.assertEqual(messages[-1], result.json['response'])
        with self.client.session_transaction() as session:
            self.assertEqual(session['user_id'], user['id'])


if __name__ == '__main__':
    unittest.main()
