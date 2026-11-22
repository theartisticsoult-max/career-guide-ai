# scratch/test_existing_features.py
import unittest
import json
import os
import shutil

# Make sure we use a test database
os.environ['SECRET_KEY'] = 'test-secret-key'

from app import app, db

class TestExistingFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def test_01_public_routes(self):
        # Index
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)

        # Categories
        res = self.client.get('/categories')
        self.assertEqual(res.status_code, 200)

        # Chatbot page
        res = self.client.get('/chatbot')
        self.assertEqual(res.status_code, 200)

        # Compare page
        res = self.client.get('/compare')
        self.assertEqual(res.status_code, 200)

        # All careers api
        res = self.client.get('/api/all-careers')
        self.assertEqual(res.status_code, 200)
        careers = json.loads(res.data)
        self.assertGreater(len(careers), 0)

        # Featured careers api
        res = self.client.get('/api/featured-careers')
        self.assertEqual(res.status_code, 200)

    def test_02_career_search_and_detail(self):
        res = self.client.get('/api/search?q=engineer')
        self.assertEqual(res.status_code, 200)
        results = json.loads(res.data)
        self.assertIsInstance(results, list)

        # Detail of first career
        res_all = self.client.get('/api/all-careers')
        first_career = json.loads(res_all.data)[0]
        cid = first_career['Career_ID']
        res_detail = self.client.get(f'/career/{cid}')
        self.assertEqual(res_detail.status_code, 200)

    def test_03_auth_and_dashboard(self):
        # Register user
        username = 'testuser_verify'
        email = 'testuser_verify@example.com'
        password = 'password123'
        
        # Clean up if exists
        conn = db.get_connection()
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()

        res = self.client.post('/register', data={
            'username': username,
            'email': email,
            'password': password,
            'full_name': 'Test User',
            'phone': '1234567890',
            'education': 'Undergraduate',
            'stream': 'Computer Science'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Login
        res = self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Access Dashboard
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)

    def test_04_quiz_submission(self):
        with self.client.session_transaction() as sess:
            user = db.get_user_by_username('testuser_verify')
            sess['user_id'] = user['id']
            sess['username'] = user['username']

        payload = {
            'stream': 'Science',
            'interests': ['coding', 'artificial intelligence'],
            'skills': ['Python', 'Problem Solving']
        }
        res = self.client.post('/api/quiz/submit', 
                               json=payload,
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success'))
        self.assertGreater(len(data.get('recommendations', [])), 0)

    def test_05_psychometric_submission(self):
        with self.client.session_transaction() as sess:
            user = db.get_user_by_username('testuser_verify')
            sess['user_id'] = user['id']
            sess['username'] = user['username']

        payload = {
            'personality': {'openness': 80, 'conscientiousness': 75},
            'interests': {'investigative': 85, 'artistic': 60},
            'aptitudes': {'analytical': 90, 'verbal': 70},
            'workStyles': {'independent': 80},
            'value_data': {'innovation': 85},
            'raw_answers': {}
        }
        res = self.client.post('/api/psychometric/submit',
                               json=payload,
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success'))
        self.assertGreater(len(data.get('career_matches', [])), 0)

    def test_06_iq_test_submission(self):
        with self.client.session_transaction() as sess:
            user = db.get_user_by_username('testuser_verify')
            sess['user_id'] = user['id']
            sess['username'] = user['username']

        payload = {
            'iq_score': 125,
            'correct_count': 25,
            'section_scores': {'logical': 85, 'numerical': 90},
            'answers': {},
            'time_taken': 1200
        }
        res = self.client.post('/api/iq-test/submit',
                               json=payload,
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data.get('success'))

if __name__ == '__main__':
    unittest.main()
