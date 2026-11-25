"""Regression tests for standards-compliant careers API JSON."""
import json
import unittest

from app import app
from app.services import career_data


class CareersApiJsonTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    @staticmethod
    def _reject_non_standard_constant(value):
        raise AssertionError(f'Non-standard JSON constant: {value}')

    def _strict_json(self, response):
        body = response.get_data(as_text=True)
        self.assertNotIn('NaN', body)
        self.assertNotIn('Infinity', body)
        return json.loads(body, parse_constant=self._reject_non_standard_constant)

    def test_career_api_responses_are_standard_json(self):
        requests = (
            ('GET', '/api/all-careers', None),
            ('GET', '/api/featured-careers', None),
            ('GET', '/api/category/Entertainment', None),
            ('GET', '/api/career/C074', None),
            ('GET', '/api/search?q=Entrepreneur', None),
            ('POST', '/api/compare', {'career_ids': ['C074', 'C181', 'C001']}),
        )
        for method, path, payload in requests:
            with self.subTest(method=method, path=path):
                if method == 'POST':
                    response = self.client.post(path, json=payload)
                else:
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIsInstance(self._strict_json(response), (list, dict))

    def test_missing_salary_is_null_and_valid_salary_is_preserved(self):
        response = self.client.get('/api/all-careers')
        careers = self._strict_json(response)
        by_id = {career['Career_ID']: career for career in careers}

        for career_id in ('C074', 'C181', 'C183', 'C184', 'C188', 'C189'):
            self.assertIsNone(by_id[career_id]['entry_salary_avg'])

        self.assertEqual(by_id['C001']['Entry_Salary_LPA'], '12-18')
        self.assertEqual(by_id['C001']['entry_salary_avg'], 15.0)

    def test_non_finite_numbers_are_sanitised_before_serialization(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                self.assertIsNone(career_data._json_safe_value(value))
        self.assertEqual(career_data._json_safe_value(15.0), 15.0)


if __name__ == '__main__':
    unittest.main()
