"""Question bank for the combined assessment.

Interest statements reuse the existing psychometric bank. Aptitude questions
reuse the first three questions of each existing IQ section; correct answers
live only in this server-side module and are never rendered to the client.
"""

INTEREST_STATEMENTS = [
    {'id': 'R1', 'type': 'R', 'text': 'Designing and building things with your hands'},
    {'id': 'R2', 'type': 'R', 'text': 'Repairing mechanical equipment'},
    {'id': 'R3', 'type': 'R', 'text': 'Working outdoors or with animals'},
    {'id': 'R4', 'type': 'R', 'text': 'I am practical and prefer hands-on work'},
    {'id': 'R5', 'type': 'R', 'text': 'Technical and mechanical understanding'},
    {'id': 'I1', 'type': 'I', 'text': 'Conducting scientific research or experiments'},
    {'id': 'I2', 'type': 'I', 'text': 'Analyzing data and finding patterns'},
    {'id': 'I3', 'type': 'I', 'text': 'I enjoy solving complex problems and puzzles'},
    {'id': 'I4', 'type': 'I', 'text': 'I am curious and love learning new things'},
    {'id': 'I5', 'type': 'I', 'text': 'Research and information gathering'},
    {'id': 'A1', 'type': 'A', 'text': 'Creating art, music, or writing stories'},
    {'id': 'A2', 'type': 'A', 'text': 'I am creative and enjoy thinking outside the box'},
    {'id': 'A3', 'type': 'A', 'text': 'Creativity and self-expression'},
    {'id': 'A4', 'type': 'A', 'text': 'Creative and artistic expression'},
    {'id': 'A5', 'type': 'A', 'text': 'Innovation and cutting-edge work'},
    {'id': 'S1', 'type': 'S', 'text': 'Teaching or training others'},
    {'id': 'S2', 'type': 'S', 'text': 'Helping people solve personal problems'},
    {'id': 'S3', 'type': 'S', 'text': 'Providing medical care to patients'},
    {'id': 'S4', 'type': 'S', 'text': 'I enjoy helping others and providing support'},
    {'id': 'S5', 'type': 'S', 'text': 'Helping others and making a difference'},
    {'id': 'E1', 'type': 'E', 'text': 'Starting your own business or venture'},
    {'id': 'E2', 'type': 'E', 'text': 'Negotiating and persuading others'},
    {'id': 'E3', 'type': 'E', 'text': 'I enjoy leading and directing others'},
    {'id': 'E4', 'type': 'E', 'text': 'I am competitive and strive to be the best'},
    {'id': 'E5', 'type': 'E', 'text': 'Public speaking and presentation'},
    {'id': 'C1', 'type': 'C', 'text': 'Organizing events and managing projects'},
    {'id': 'C2', 'type': 'C', 'text': 'I pay close attention to details and accuracy'},
    {'id': 'C3', 'type': 'C', 'text': 'I am organized and like structure in my work'},
    {'id': 'C4', 'type': 'C', 'text': 'Project planning and organization'},
    {'id': 'C5', 'type': 'C', 'text': 'I prefer routine and predictable tasks'},
]

APTITUDE_QUESTIONS = [
    {'id': 'N1', 'section': 'numerical', 'text': 'What is 15% of 200?',
     'options': ['25', '30', '35', '40'], 'correct': 1},
    {'id': 'N2', 'section': 'numerical', 'text': 'If a train travels 300 km in 5 hours, what is its average speed?',
     'options': ['50 km/h', '60 km/h', '70 km/h', '80 km/h'], 'correct': 1},
    {'id': 'N3', 'section': 'numerical', 'text': 'Solve: 8 × (5 + 3) - 4 = ?',
     'options': ['60', '64', '68', '72'], 'correct': 0},
    {'id': 'V1', 'section': 'verbal', 'text': 'Choose the word most similar in meaning to "Benevolent":',
     'options': ['Kind', 'Strict', 'Angry', 'Greedy'], 'correct': 0},
    {'id': 'V2', 'section': 'verbal', 'text': 'Complete the analogy: Doctor is to Hospital as Teacher is to ______',
     'options': ['School', 'Office', 'Library', 'Classroom'], 'correct': 0},
    {'id': 'V3', 'section': 'verbal', 'text': 'Choose the word opposite in meaning to "Optimistic":',
     'options': ['Hopeful', 'Positive', 'Pessimistic', 'Cheerful'], 'correct': 2},
    {'id': 'L1', 'section': 'logical', 'text': 'Complete the series: 2, 6, 12, 20, ?',
     'options': ['28', '30', '32', '34'], 'correct': 0},
    {'id': 'L2', 'section': 'logical', 'text': 'If A is taller than B, and B is taller than C, which statement is true?',
     'options': ['A is shortest', 'C is tallest', 'A is taller than C', 'B is tallest'], 'correct': 2},
    {'id': 'L3', 'section': 'logical', 'text': 'Find the missing number: 3, 9, 27, 81, ?',
     'options': ['162', '243', '324', '405'], 'correct': 1},
    {'id': 'S1', 'section': 'spatial', 'text': 'Which shape would complete the pattern?',
     'options': ['Square', 'Triangle', 'Circle', 'Rectangle'], 'correct': 1},
    {'id': 'S2', 'section': 'spatial', 'text': 'If you rotate the shape 90 degrees clockwise, what do you get?',
     'options': ['Up-Right', 'Down-Right', 'Down-Left', 'Up-Left'], 'correct': 1},
    {'id': 'S3', 'section': 'spatial', 'text': 'Which of the following is a 3D shape?',
     'options': ['Circle', 'Square', 'Cube', 'Triangle'], 'correct': 2},
]

PREFERENCE_QUESTIONS = [
    {
        'id': 'salary_priority', 'text': 'How important is a high salary?',
        'options': [{'value': 'low', 'label': 'Not a priority'},
                    {'value': 'medium', 'label': 'Somewhat important'},
                    {'value': 'high', 'label': 'Very important'}],
    },
    {
        'id': 'team_style', 'text': 'Do you prefer working with others or alone?',
        'options': [{'value': 'team', 'label': 'With a team'},
                    {'value': 'solo', 'label': 'Independently'}],
    },
    {
        'id': 'work_setting', 'text': 'Do you prefer a desk job or field work?',
        'options': [{'value': 'desk', 'label': 'Desk-based'},
                    {'value': 'field', 'label': 'Field-based'}],
    },
    {
        'id': 'location', 'text': 'Where would you like to work?',
        'options': [{'value': 'city', 'label': 'Large city'},
                    {'value': 'town', 'label': 'Small town'},
                    {'value': 'remote', 'label': 'Remote'}],
    },
    {
        'id': 'stability', 'text': 'Do you prefer stability or risk?',
        'options': [{'value': 'stable', 'label': 'Stable and predictable'},
                    {'value': 'risk', 'label': 'Fast-changing and risky'}],
    },
    {
        'id': 'study_years', 'text': 'How many years are you willing to study after class 12?',
        'options': [{'value': '0-2', 'label': '0-2 years'},
                    {'value': '3-5', 'label': '3-5 years'},
                    {'value': '6+', 'label': '6 or more years'}],
    },
]

APTITUDE_SECTIONS = ('numerical', 'verbal', 'logical', 'spatial')
RIASEC_TYPES = ('R', 'I', 'A', 'S', 'E', 'C')
