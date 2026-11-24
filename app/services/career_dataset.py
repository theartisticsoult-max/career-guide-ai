"""Domain metadata for the career catalogue.

Every existing row and column is preserved. The enrichment below fills the
additional recommendation columns deterministically, grouped by domain and
category so values are realistic and repeatable.
"""
import re

import pandas as pd

NEW_COLUMNS = [
    'domain',
    'riasec_R', 'riasec_I', 'riasec_A', 'riasec_S', 'riasec_E', 'riasec_C',
    'apt_numerical', 'apt_verbal', 'apt_logical', 'apt_spatial',
    'stages', 'work_style', 'key_exams',
]

RIASEC_KEYS = ('riasec_R', 'riasec_I', 'riasec_A', 'riasec_S', 'riasec_E', 'riasec_C')
APTITUDE_KEYS = ('apt_numerical', 'apt_verbal', 'apt_logical', 'apt_spatial')

DOMAIN_BY_CATEGORY = {
    'Information Technology': 'tech',
    'Core Engineering': 'tech',
    'Emerging Technologies': 'tech',
    'Healthcare': 'healthcare',
    'Management': 'business/finance',
    'Banking Finance': 'business/finance',
    'Retail': 'business/finance',
    'Media': 'creative/media',
    'Arts': 'creative/media',
    'Entertainment': 'creative/media',
    'Law': 'law/govt',
    'Government': 'law/govt',
    'Defence': 'law/govt',
    'Education': 'education/social',
    'Social Work': 'education/social',
    'Science': 'science/research',
    'Skilled Trades': 'skilled/vocational',
    'Sports': 'sports/agri/hospitality',
    'Agriculture': 'sports/agri/hospitality',
    'Hospitality': 'sports/agri/hospitality',
}

DOMAIN_PROFILES = {
    # domain: (R, I, A, S, E, C, num, verbal, logical, spatial)
    'tech': (0.55, 0.80, 0.30, 0.25, 0.35, 0.60, 0.75, 0.45, 0.90, 0.65),
    'healthcare': (0.45, 0.75, 0.20, 0.85, 0.40, 0.65, 0.65, 0.60, 0.80, 0.55),
    'business/finance': (0.20, 0.45, 0.25, 0.45, 0.85, 0.80, 0.85, 0.65, 0.75, 0.35),
    'creative/media': (0.25, 0.40, 0.90, 0.35, 0.55, 0.25, 0.25, 0.75, 0.50, 0.80),
    'law/govt': (0.20, 0.50, 0.35, 0.60, 0.75, 0.80, 0.35, 0.90, 0.85, 0.30),
    'education/social': (0.15, 0.45, 0.45, 0.90, 0.50, 0.45, 0.40, 0.85, 0.65, 0.35),
    'science/research': (0.40, 0.90, 0.35, 0.25, 0.25, 0.55, 0.80, 0.60, 0.90, 0.70),
    'skilled/vocational': (0.90, 0.45, 0.40, 0.35, 0.30, 0.55, 0.55, 0.35, 0.60, 0.90),
    'sports/agri/hospitality': (0.70, 0.35, 0.35, 0.70, 0.50, 0.40, 0.40, 0.50, 0.55, 0.60),
}

# Category-level adjustments so careers inside a domain stay distinct.
CATEGORY_TWEAKS = {
    'Information Technology': {'riasec_I': 0.90, 'apt_logical': 0.95},
    'Emerging Technologies': {'riasec_I': 0.92, 'riasec_A': 0.45, 'apt_spatial': 0.75},
    'Core Engineering': {'riasec_R': 0.75, 'apt_spatial': 0.85},
    'Healthcare': {'riasec_S': 0.90, 'apt_verbal': 0.70},
    'Management': {'riasec_E': 0.92, 'riasec_C': 0.70},
    'Banking Finance': {'riasec_C': 0.92, 'apt_numerical': 0.92},
    'Retail': {'riasec_E': 0.88, 'riasec_S': 0.65},
    'Media': {'riasec_A': 0.92, 'apt_verbal': 0.85},
    'Arts': {'riasec_A': 0.95, 'apt_spatial': 0.88},
    'Entertainment': {'riasec_A': 0.88, 'riasec_E': 0.70},
    'Law': {'riasec_E': 0.82, 'apt_verbal': 0.95},
    'Government': {'riasec_C': 0.88, 'apt_verbal': 0.80},
    'Defence': {'riasec_R': 0.65, 'apt_logical': 0.75},
    'Education': {'riasec_S': 0.95, 'riasec_A': 0.55},
    'Social Work': {'riasec_S': 0.95, 'riasec_E': 0.55},
    'Science': {'riasec_I': 0.95, 'apt_logical': 0.95},
    'Skilled Trades': {'riasec_R': 0.95, 'apt_spatial': 0.92},
    'Sports': {'riasec_R': 0.88, 'riasec_E': 0.60},
    'Agriculture': {'riasec_R': 0.82, 'riasec_I': 0.55},
    'Hospitality': {'riasec_S': 0.88, 'riasec_E': 0.65},
}

STAGES_BY_CATEGORY = {
    'Skilled Trades': 'class10|class12|college',
    'Hospitality': 'class10|class12|college',
    'Retail': 'class10|class12|college',
    'Agriculture': 'class10|class12|college',
    'Sports': 'class10|class12|college',
    'Arts': 'class10|class12|college',
    'Entertainment': 'class10|class12|college',
}

DEFAULT_STAGES = 'class12|college'

WORK_STYLE_BY_DOMAIN = {
    'tech': 'analytical|independent|structured',
    'healthcare': 'team|precision|service',
    'business/finance': 'team|competitive|structured',
    'creative/media': 'creative|independent|flexible',
    'law/govt': 'structured|assertive|team',
    'education/social': 'service|team|community',
    'science/research': 'analytical|independent|patient',
    'skilled/vocational': 'hands-on|field|practical',
    'sports/agri/hospitality': 'field|team|active',
}

EXAM_PATTERNS = (
    ('NEET', r'neet'),
    ('JEE', r'jee|\biet\b|state cet'),
    ('GATE', r'gate'),
    ('CAT', r'\bcat\b|\bxat\b|\bmat\b'),
    ('CLAT', r'clat'),
    ('UPSC', r'upsc|psc'),
    ('NIFT', r'nift'),
    ('NDA', r'nda|cds|afcat'),
    ('ICAR', r'icar'),
    ('NCHMCT', r'nchmct'),
    ('NCVT', r'ncvt|scvt'),
)

EXAM_BY_CATEGORY = {
    'Information Technology': 'JEE',
    'Core Engineering': 'JEE',
    'Healthcare': 'NEET',
    'Law': 'CLAT',
    'Government': 'UPSC',
    'Defence': 'NDA',
    'Management': 'CAT',
    'Banking Finance': 'CAT',
    'Science': 'JEE',
    'Education': 'none',
    'Social Work': 'none',
    'Media': 'none',
    'Arts': 'NIFT',
    'Entertainment': 'none',
    'Skilled Trades': 'NCVT',
    'Agriculture': 'ICAR',
    'Hospitality': 'NCHMCT',
    'Sports': 'none',
    'Retail': 'none',
    'Emerging Technologies': 'JEE',
}


def normalise_exams(text, category):
    """Map free-text entrance exam info to a short, consistent tag."""
    value = str(text or '')
    lowered = value.lower()
    for tag, pattern in EXAM_PATTERNS:
        if re.search(pattern, lowered):
            return tag
    return EXAM_BY_CATEGORY.get(category, 'none')


def enrich_career_df(df):
    """Return a copy of ``df`` with all recommendation columns filled."""
    enriched = df.copy()
    for index, row in enriched.iterrows():
        category = row['Category']
        domain = DOMAIN_BY_CATEGORY.get(category, 'science/research')
        profile = list(DOMAIN_PROFILES[domain])
        for key, value in CATEGORY_TWEAKS.get(category, {}).items():
            position = (RIASEC_KEYS + APTITUDE_KEYS).index(key)
            profile[position] = value

        enriched.at[index, 'domain'] = domain
        for key, value in zip(RIASEC_KEYS + APTITUDE_KEYS, profile):
            enriched.at[index, key] = round(float(value), 2)
        enriched.at[index, 'stages'] = STAGES_BY_CATEGORY.get(category, DEFAULT_STAGES)
        enriched.at[index, 'work_style'] = WORK_STYLE_BY_DOMAIN[domain]
        enriched.at[index, 'key_exams'] = normalise_exams(row.get('Entrance_Exams'), category)
    return enriched


def ensure_dataset_columns(df):
    """Enrich only when the CSV has not been materialised yet."""
    if all(column in df.columns for column in NEW_COLUMNS):
        return df
    return enrich_career_df(df)


def validate_dataset(df):
    """Return a list of human-readable validation errors."""
    errors = []
    missing_columns = [name for name in NEW_COLUMNS if name not in df.columns]
    if missing_columns:
        errors.append('Missing columns: ' + ', '.join(missing_columns))
        return errors

    for column in RIASEC_KEYS + APTITUDE_KEYS:
        values = pd.to_numeric(df[column], errors='coerce')
        if values.isna().any():
            errors.append(f'{column} has empty or non-numeric values')
        elif ((values < 0) | (values > 1)).any():
            errors.append(f'{column} has values outside 0-1')

    for column in ('domain', 'stages', 'work_style', 'key_exams'):
        if df[column].isna().any() or (df[column].astype(str).str.strip() == '').any():
            errors.append(f'{column} has empty values')

    valid_stages = {'class10', 'class12', 'college'}
    for stage in df['stages'].astype(str):
        parts = set(stage.split('|'))
        if not parts or not parts.issubset(valid_stages):
            errors.append(f'Invalid stages value: {stage}')

    domains = set(df['domain'].unique())
    required = set(DOMAIN_PROFILES)
    if not required.issubset(domains):
        errors.append('Missing domains: ' + ', '.join(sorted(required - domains)))
    for domain, count in df['domain'].value_counts().items():
        if count < 4:
            errors.append(f'Domain {domain} has only {count} careers')
    return errors
