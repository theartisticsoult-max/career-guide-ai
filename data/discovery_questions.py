"""The single 12-question career discovery assessment.

Answers are mapped to the same score shapes used by the legacy assessment so
the code-side recommender can stay shared. This is exploratory guidance, not a
psychometric or aptitude diagnosis.
"""

DISCOVERY_QUESTIONS = [
    {
        'id': 'd1',
        'text': 'Where are you in your education or career right now?',
        'help': 'Choose the closest option.',
        'type': 'single',
        'profile': {'stage': {'class10': 'class10', 'class12': 'class12',
                              'college': 'college', 'working': 'college'}},
        'options': [
            {'value': 'class10', 'label': 'Class 10 or below'},
            {'value': 'class12', 'label': 'Class 11 or 12'},
            {'value': 'college', 'label': 'College or university'},
            {'value': 'working', 'label': 'Working / changing career'},
        ],
    },
    {
        'id': 'd2',
        'text': 'Which stream or background do you know best?',
        'help': 'Pick the one you have studied or worked in most.',
        'type': 'single',
        'profile': {'stream': True},
        'options': [
            {'value': 'Science', 'label': 'Science'},
            {'value': 'Commerce', 'label': 'Commerce / Business'},
            {'value': 'Arts', 'label': 'Arts / Humanities'},
            {'value': 'Engineering', 'label': 'Engineering / Technology'},
            {'value': 'Other', 'label': 'Something else'},
            {'value': 'Not sure', 'label': 'Not sure'},
        ],
    },
    {
        'id': 'd3',
        'text': 'Which activities sound most interesting?',
        'help': 'Choose up to 3.',
        'type': 'multi',
        'max': 3,
        'riasec': True,
        'profile': {'interests_text': True},
        'options': [
            {'value': 'R', 'label': 'Building, fixing or working with my hands', 'riasec': {'R': 1}},
            {'value': 'I', 'label': 'Investigating questions and solving puzzles', 'riasec': {'I': 1}},
            {'value': 'A', 'label': 'Creating art, writing or designing', 'riasec': {'A': 1}},
            {'value': 'S', 'label': 'Helping, teaching or caring for people', 'riasec': {'S': 1}},
            {'value': 'E', 'label': 'Leading, persuading or starting things', 'riasec': {'E': 1}},
            {'value': 'C', 'label': 'Organising, planning and working with data', 'riasec': {'C': 1}},
        ],
    },
    {
        'id': 'd4',
        'text': 'Which school or work subject do you like most?',
        'help': 'Choose one.',
        'type': 'single',
        'riasec': True,
        'aptitude': True,
        'options': [
            {'value': 'math', 'label': 'Maths', 'aptitude': {'numerical': 1}, 'riasec': {'I': 1}},
            {'value': 'science', 'label': 'Science', 'aptitude': {'logical': 1}, 'riasec': {'I': 1}},
            {'value': 'english', 'label': 'English or a language', 'aptitude': {'verbal': 1}, 'riasec': {'A': 1}},
            {'value': 'social', 'label': 'History or social studies', 'aptitude': {'verbal': 1}, 'riasec': {'S': 1}},
            {'value': 'business', 'label': 'Business or commerce', 'aptitude': {'numerical': 1}, 'riasec': {'E': 1}},
            {'value': 'art', 'label': 'Art, music or design', 'aptitude': {'spatial': 1}, 'riasec': {'A': 1}},
            {'value': 'practical', 'label': 'A practical or vocational subject', 'aptitude': {'spatial': 1}, 'riasec': {'R': 1}},
        ],
    },
    {
        'id': 'd5',
        'text': 'How do you like to solve a problem?',
        'help': 'Choose the way that feels most natural.',
        'type': 'single',
        'aptitude': True,
        'options': [
            {'value': 'numbers', 'label': 'Work through numbers and figures', 'aptitude': {'numerical': 1}},
            {'value': 'words', 'label': 'Talk it through or write it down', 'aptitude': {'verbal': 1}},
            {'value': 'puzzles', 'label': 'Find the logic or the pattern', 'aptitude': {'logical': 1}},
            {'value': 'pictures', 'label': 'Sketch, map or visualise it', 'aptitude': {'spatial': 1}},
            {'value': 'people', 'label': 'Ask people and understand their view', 'aptitude': {'verbal': 1}},
        ],
    },
    {
        'id': 'd6',
        'text': 'Where would you like to work most days?',
        'help': 'Choose one.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'field', 'label': 'Outdoors, in the field or on site', 'prefs': {'work_setting': 1.0}},
            {'value': 'desk', 'label': 'At a desk or in an office', 'prefs': {'work_setting': 0.0}},
            {'value': 'mixed', 'label': 'A mix of both', 'prefs': {'work_setting': 0.5}},
        ],
    },
    {
        'id': 'd7',
        'text': 'Do you prefer working with a team or on your own?',
        'help': 'Choose one.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'team', 'label': 'Mostly with a team', 'prefs': {'team_style': 1.0}},
            {'value': 'solo', 'label': 'Mostly independently', 'prefs': {'team_style': 0.0}},
            {'value': 'mixed', 'label': 'A mix of both', 'prefs': {'team_style': 0.5}},
        ],
    },
    {
        'id': 'd8',
        'text': 'Do you prefer a steady routine or variety?',
        'help': 'Choose one.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'stable', 'label': 'A predictable routine', 'prefs': {'stability': 1.0}},
            {'value': 'risk', 'label': 'Lots of change and variety', 'prefs': {'stability': 0.0}},
        ],
    },
    {
        'id': 'd9',
        'text': 'How long are you willing to study or train?',
        'help': 'Include college, diplomas or professional courses.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': '0-2', 'label': 'Up to 2 years'},
            {'value': '3-5', 'label': '3 to 5 years'},
            {'value': '6+', 'label': 'More than 5 years'},
        ],
    },
    {
        'id': 'd10',
        'text': 'What matters most in a career?',
        'help': 'Choose one.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'high', 'label': 'A high income', 'prefs': {'salary_priority': 1.0}},
            {'value': 'medium', 'label': 'A balance of income and meaning', 'prefs': {'salary_priority': 0.6}},
            {'value': 'low', 'label': 'Meaning and service more than income', 'prefs': {'salary_priority': 0.2}},
        ],
    },
    {
        'id': 'd11',
        'text': 'Where would you like your work to be based?',
        'help': 'Choose one.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'city', 'label': 'A big city', 'prefs': {'location': 0.2}},
            {'value': 'town', 'label': 'A town or smaller city', 'prefs': {'location': 0.6}},
            {'value': 'remote', 'label': 'Remote or flexible location', 'prefs': {'location': 1.0}},
        ],
    },
    {
        'id': 'd12',
        'text': 'Would you consider a career that needs a licence, exam or registration?',
        'help': 'Some careers (for example medicine or law) require formal registration.',
        'type': 'single',
        'prefs': True,
        'options': [
            {'value': 'yes', 'label': 'Yes, I am open to that', 'prefs': {'stability': 1.0}},
            {'value': 'no', 'label': 'I would rather avoid it', 'prefs': {'stability': 0.0}},
            {'value': 'unsure', 'label': 'Not sure yet', 'prefs': {'stability': 0.5}},
        ],
    },
]

RIASEC_LETTERS = ('R', 'I', 'A', 'S', 'E', 'C')
APTITUDE_SECTIONS = ('numerical', 'verbal', 'logical', 'spatial')
QUESTION_BY_ID = {question['id']: question for question in DISCOVERY_QUESTIONS}


def public_questions():
    """Return questions without server-side scoring hints."""
    return [
        {
            'id': question['id'],
            'text': question['text'],
            'help': question['help'],
            'type': question['type'],
            'max': question.get('max'),
            'options': [
                {'value': option['value'], 'label': option['label']}
                for option in question['options']
            ],
        }
        for question in DISCOVERY_QUESTIONS
    ]
