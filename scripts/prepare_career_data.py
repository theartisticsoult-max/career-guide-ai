"""Seed step: materialise the recommendation columns into data/career.csv.

Safe to re-run: existing rows and columns are never removed.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.career_data import CAREER_CSV
from app.services.career_dataset import enrich_career_df, validate_dataset


def main():
    original = pd.read_csv(CAREER_CSV)
    enriched = enrich_career_df(original)
    errors = validate_dataset(enriched)
    if errors:
        raise SystemExit('Dataset validation failed:\n' + '\n'.join(errors))

    for column in original.columns:
        if not enriched[column].equals(original[column]):
            raise SystemExit(f'Existing column changed: {column}')

    enriched.to_csv(CAREER_CSV, index=False)
    print(f'Updated {len(enriched)} careers with {len(enriched.columns)} columns')


if __name__ == '__main__':
    main()
