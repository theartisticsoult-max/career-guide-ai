"""Tests for Phase 5: enriched careers dataset."""
import unittest

import pandas as pd

from app.services import career_data
from app.services.career_dataset import (
    APTITUDE_KEYS,
    DOMAIN_PROFILES,
    NEW_COLUMNS,
    RIASEC_KEYS,
    enrich_career_df,
    normalise_exams,
    validate_dataset,
)

ORIGINAL_COLUMNS = [
    'Career_ID', 'Category', 'Career_Name', 'Min_Education', 'Preferred_Stream',
    'Required_Degree', 'Entrance_Exams', 'Duration_Years', 'Key_Technical_Skills',
    'Key_Soft_Skills', 'Entry_Salary_LPA', 'Mid_Salary_LPA', 'Senior_Salary_LPA',
    'Job_Outlook', 'Top_Recruiters_India',
]


class TestCareerDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(career_data.CAREER_CSV)

    def test_dataset_shape_and_original_columns_preserved(self):
        self.assertEqual(len(self.df), 300)
        for column in ORIGINAL_COLUMNS:
            self.assertIn(column, self.df.columns)

    def test_all_new_columns_present_and_valid(self):
        self.assertEqual(validate_dataset(self.df), [])
        for column in NEW_COLUMNS:
            self.assertIn(column, self.df.columns)
        for column in RIASEC_KEYS + APTITUDE_KEYS:
            values = pd.to_numeric(self.df[column], errors='coerce')
            self.assertFalse(values.isna().any(), column)
            self.assertTrue(((values >= 0) & (values <= 1)).all(), column)

    def test_all_domains_present_with_at_least_four_careers(self):
        counts = self.df['domain'].value_counts()
        for domain in DOMAIN_PROFILES:
            self.assertIn(domain, counts.index)
            self.assertGreaterEqual(counts[domain], 4)

    def test_text_fields_are_filled_and_stages_are_valid(self):
        for column in ('domain', 'stages', 'work_style', 'key_exams'):
            self.assertFalse(self.df[column].isna().any(), column)
            self.assertFalse((self.df[column].astype(str).str.strip() == '').any(), column)
        allowed = {'class10', 'class12', 'college'}
        for value in self.df['stages']:
            self.assertTrue(set(value.split('|')).issubset(allowed))

    def test_exam_normalisation(self):
        self.assertEqual(normalise_exams('NEET-PG', 'Healthcare'), 'NEET')
        self.assertEqual(normalise_exams('JEE/State CET', 'Core Engineering'), 'JEE')
        self.assertEqual(normalise_exams('CLAT/state', 'Law'), 'CLAT')
        self.assertEqual(normalise_exams('CAT/XAT', 'Management'), 'CAT')
        self.assertEqual(normalise_exams('', 'Social Work'), 'none')

    def test_enrichment_is_idempotent(self):
        again = enrich_career_df(self.df)
        for column in ORIGINAL_COLUMNS + NEW_COLUMNS:
            pd.testing.assert_series_equal(again[column], self.df[column])

    def test_loader_exposes_enriched_fields(self):
        career = career_data.get_career('C001')
        for column in NEW_COLUMNS:
            self.assertIn(column, career)
        self.assertEqual(career['domain'], 'healthcare')


if __name__ == '__main__':
    unittest.main()
