"""Career dataset access and code-based ranking.

All matching/scoring happens here in Python. The language model is never
responsible for choosing or ordering careers.
"""
import os

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAREER_CSV = os.path.join(PROJECT_ROOT, 'data', 'career.csv')

career_df = None
vectorizer = None
career_vectors = None


def parse_salary(salary_str):
    """Parse salary string to average value"""
    if pd.isna(salary_str) or salary_str == 'Varies':
        return None
    try:
        if '-' in str(salary_str):
            low, high = str(salary_str).split('-')
            return (float(low) + float(high)) / 2
        return float(salary_str)
    except:
        return None


def load_career_data():
    """Load and prepare career data"""
    global career_df, vectorizer, career_vectors

    try:
        career_df = pd.read_csv(CAREER_CSV)
        print(f"Loaded {len(career_df)} careers")

        # Prepare text features
        career_df['combined_features'] = (
            career_df['Category'].fillna('') + ' ' +
            career_df['Career_Name'].fillna('') + ' ' +
            career_df['Key_Technical_Skills'].fillna('') + ' ' +
            career_df['Key_Soft_Skills'].fillna('') + ' ' +
            career_df['Preferred_Stream'].fillna('')
        )

        # Parse salary ranges
        career_df['entry_salary_avg'] = career_df['Entry_Salary_LPA'].apply(parse_salary)

        # Create TF-IDF vectors
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        career_vectors = vectorizer.fit_transform(career_df['combined_features'].fillna(''))

        return True
    except Exception as e:
        print(f"Error loading data: {e}")
        return False


def is_loaded():
    """Return whether the career dataset has been loaded."""
    return career_df is not None


def get_categories():
    """Return the sorted list of career categories."""
    if career_df is None:
        return []
    return sorted(career_df['Category'].unique().tolist())


def is_valid_category(category):
    """Return whether the category exists in the dataset."""
    if career_df is None:
        return False
    return category in career_df['Category'].unique().tolist()


def get_career(career_id):
    """Return one career as a dict, or None when it does not exist."""
    if career_df is None:
        return None
    career = career_df[career_df['Career_ID'] == career_id]
    if career.empty:
        return None
    return career.iloc[0].to_dict()


def get_all_careers():
    """Return every career as records."""
    if career_df is None:
        return []
    return career_df.to_dict('records')


def get_featured_careers():
    """Return the six highest-entry-salary careers with a known salary."""
    if career_df is None:
        return []
    featured = career_df[career_df['entry_salary_avg'].notna()].sort_values(
        'entry_salary_avg', ascending=False
    ).head(6)
    return featured.to_dict('records')


def get_careers_by_category(category):
    """Return all careers in a category."""
    if career_df is None:
        return []
    return career_df[career_df['Category'] == category].to_dict('records')


def get_compare_options():
    """Return the short career list used by the comparison page."""
    if career_df is None:
        return []
    return career_df[['Career_ID', 'Career_Name', 'Category']].to_dict('records')


def compare_careers(career_ids):
    """Return the requested careers, in the order requested."""
    if career_df is None:
        return []
    careers = []
    for cid in career_ids:
        career = career_df[career_df['Career_ID'] == cid]
        if not career.empty:
            careers.append(career.iloc[0].to_dict())
    return careers


def search_careers(query):
    """Search careers by name, category or technical skills."""
    if career_df is None or len(query) < 2:
        return []
    query_lower = query.lower()
    mask = (
        career_df['Career_Name'].str.lower().str.contains(query_lower, na=False) |
        career_df['Category'].str.lower().str.contains(query_lower, na=False) |
        career_df['Key_Technical_Skills'].str.lower().str.contains(query_lower, na=False)
    )
    return career_df[mask].head(10).to_dict('records')


def get_recommendations(preferences, top_n=12):
    """Generate career recommendations based on preferences"""
    global career_df, career_vectors, vectorizer

    if career_df is None or career_vectors is None:
        return []

    user_text = []

    if preferences.get('stream') and preferences['stream'] != 'Any':
        user_text.append(preferences['stream'])

    if preferences.get('interests'):
        if isinstance(preferences['interests'], list):
            user_text.extend(preferences['interests'])
        else:
            user_text.append(preferences['interests'])

    if preferences.get('skills'):
        if isinstance(preferences['skills'], list):
            user_text.extend(preferences['skills'])
        else:
            user_text.append(preferences['skills'])

    user_profile = ' '.join(user_text)

    if not user_profile.strip():
        recommendations = career_df.head(top_n).to_dict('records')
        for i, rec in enumerate(recommendations):
            rec['match_score'] = 50 + np.random.randint(0, 30)
        return recommendations

    try:
        user_vector = vectorizer.transform([user_profile])
        similarities = cosine_similarity(user_vector, career_vectors).flatten()

        top_indices = similarities.argsort()[-top_n:][::-1]

        recommendations = []
        for idx in top_indices:
            career = career_df.iloc[idx].to_dict()
            career['match_score'] = round(similarities[idx] * 100, 1)
            recommendations.append(career)

        return recommendations
    except Exception as e:
        print(f"Error in get_recommendations: {e}")
        return career_df.head(top_n).to_dict('records')


def get_similar_careers(career_id, top_n=4):
    """Get careers similar to given career"""
    global career_df, career_vectors, vectorizer

    if career_df is None or career_vectors is None:
        return []

    career_idx = career_df[career_df['Career_ID'] == career_id].index
    if len(career_idx) == 0:
        return []

    idx = career_idx[0]

    similarities = cosine_similarity(career_vectors[idx], career_vectors).flatten()

    top_indices = similarities.argsort()[-top_n-1:][::-1][1:top_n+1]

    similar = []
    for i in top_indices:
        career = career_df.iloc[i].to_dict()
        career['match_score'] = round(similarities[i] * 100, 1)
        similar.append(career)

    return similar
