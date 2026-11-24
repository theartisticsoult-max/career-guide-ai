"""Psychometric and IQ question banks (static data)."""


# Questions data
PERSONALITY_QUESTIONS = [
    "I enjoy meeting new people and socializing",
    "I prefer to work independently rather than in teams",
    "I pay close attention to details and accuracy",
    "I enjoy solving complex problems and puzzles",
    "I am organized and like structure in my work",
    "I am creative and enjoy thinking outside the box",
    "I remain calm under pressure and stress",
    "I enjoy helping others and providing support",
    "I am curious and love learning new things",
    "I prefer routine and predictable tasks",
    "I am competitive and strive to be the best",
    "I am empathetic and understand others' feelings",
    "I enjoy leading and directing others",
    "I am practical and prefer hands-on work",
    "I am analytical and data-driven in decision making"
]

INTEREST_QUESTIONS = [
    "Conducting scientific research or experiments",
    "Designing and building things with your hands",
    "Teaching or training others",
    "Starting your own business or venture",
    "Creating art, music, or writing stories",
    "Analyzing data and finding patterns",
    "Helping people solve personal problems",
    "Working with computers and technology",
    "Organizing events and managing projects",
    "Working outdoors or with animals",
    "Negotiating and persuading others",
    "Repairing mechanical equipment",
    "Studying history, culture, or languages",
    "Providing medical care to patients",
    "Developing new software or applications"
]

APTITUDE_QUESTIONS = [
    "Mathematical and numerical reasoning",
    "Verbal and written communication",
    "Logical and analytical thinking",
    "Creative and artistic expression",
    "Technical and mechanical understanding",
    "Leadership and people management",
    "Problem-solving under pressure",
    "Attention to detail and precision",
    "Public speaking and presentation",
    "Research and information gathering",
    "Project planning and organization",
    "Multitasking and time management",
    "Adaptability and learning new skills",
    "Empathy and emotional intelligence",
    "Strategic thinking and planning"
]

WORK_STYLE_QUESTIONS = [
    "Flexible working hours and remote work",
    "Collaborative team environment",
    "Fast-paced and dynamic work",
    "Stable and predictable routine",
    "Opportunity for travel",
    "Work-life balance",
    "High salary and financial rewards",
    "Recognition and appreciation",
    "Continuous learning opportunities",
    "Making a positive social impact"
]

VALUES_QUESTIONS = [
    "Financial security and stability",
    "Helping others and making a difference",
    "Prestige and recognition",
    "Creativity and self-expression",
    "Independence and autonomy",
    "Continuous growth and learning",
    "Work-life balance and family time",
    "Innovation and cutting-edge work",
    "Environmental sustainability",
    "Social justice and equality"
]

# Add to app.py after the existing questions

# IQ Test Questions
# app.py - Add these updated question sets

# IQ Test Questions with correct answers
IQ_LOGICAL_QUESTIONS = [
    {'text': 'If all Bloops are Razzies and all Razzies are Lazzies, then all Bloops are definitely Lazzies. This statement is:', 
     'options': ['True', 'False', 'Uncertain', 'Cannot be determined'],
     'correct': 0},
    {'text': 'Complete the series: 2, 6, 12, 20, ?', 
     'options': ['28', '30', '32', '34'],
     'correct': 0},
    {'text': 'Which number is the odd one out? 2, 5, 10, 17, 26, 37, 50', 
     'options': ['2', '26', '37', '50'],
     'correct': 3},
    {'text': 'If A is taller than B, and B is taller than C, then which statement is true?', 
     'options': ['A is shortest', 'C is tallest', 'A is taller than C', 'B is tallest'],
     'correct': 2},
    {'text': 'Find the missing number: 3, 9, 27, 81, ?', 
     'options': ['162', '243', '324', '405'],
     'correct': 1},
    {'text': 'Which word does not belong? Apple, Banana, Orange, Carrot, Mango', 
     'options': ['Apple', 'Banana', 'Carrot', 'Mango'],
     'correct': 2},
    {'text': 'If NOON is coded as 14151414, then what is MORNING coded as?', 
     'options': ['131518149147', '13151814914', '1315189147', '131518914'],
     'correct': 0},
    {'text': 'Which shape completes the pattern? (Pattern recognition question)', 
     'options': ['Circle', 'Square', 'Triangle', 'Hexagon'],
     'correct': 2}
]

IQ_NUMERICAL_QUESTIONS = [
    {'text': 'What is 15% of 200?', 'options': ['25', '30', '35', '40'], 'correct': 1},
    {'text': 'If a train travels 300 km in 5 hours, what is its average speed?', 
     'options': ['50 km/h', '60 km/h', '70 km/h', '80 km/h'], 'correct': 1},
    {'text': 'Solve: 8 × (5 + 3) - 4 = ?', 'options': ['60', '64', '68', '72'], 'correct': 0},
    {'text': 'What is the square root of 144?', 'options': ['10', '11', '12', '13'], 'correct': 2},
    {'text': 'A shirt costs ₹1200 after a 20% discount. What was the original price?', 
     'options': ['₹1400', '₹1440', '₹1500', '₹1600'], 'correct': 2},
    {'text': 'What is the next number: 1, 4, 9, 16, 25, ?', 'options': ['30', '32', '36', '49'], 'correct': 2},
    {'text': 'If 3 workers can build a wall in 10 days, how many workers are needed to build it in 5 days?', 
     'options': ['5', '6', '7', '8'], 'correct': 1},
    {'text': 'What is 2/3 of 90?', 'options': ['30', '45', '60', '75'], 'correct': 2}
]

IQ_VERBAL_QUESTIONS = [
    {'text': 'Choose the word that is most similar in meaning to "Benevolent":', 
     'options': ['Kind', 'Strict', 'Angry', 'Greedy'], 'correct': 0},
    {'text': 'Complete the analogy: Doctor is to Hospital as Teacher is to ______', 
     'options': ['School', 'Office', 'Library', 'Classroom'], 'correct': 0},
    {'text': 'Choose the word that is opposite in meaning to "Optimistic":', 
     'options': ['Hopeful', 'Positive', 'Pessimistic', 'Cheerful'], 'correct': 2},
    {'text': 'Select the correct spelling:', 
     'options': ['Accommodate', 'Acommodate', 'Accommodate', 'Acommodate'], 'correct': 0},
    {'text': 'Choose the word that best fits: The ________ of the movie left the audience confused.', 
     'options': ['Plot', 'Ending', 'Beginning', 'Title'], 'correct': 1},
    {'text': 'Select the synonym of "Magnificent":', 
     'options': ['Ordinary', 'Splendid', 'Average', 'Mediocre'], 'correct': 1},
    {'text': 'Complete the sentence: She is _______ than her sister.', 
     'options': ['Tall', 'Taller', 'Tallest', 'More tall'], 'correct': 1},
    {'text': 'Choose the antonym of "Fragile":', 
     'options': ['Weak', 'Delicate', 'Strong', 'Breakable'], 'correct': 2}
]

IQ_SPATIAL_QUESTIONS = [
    {'text': 'Which shape would complete the pattern?', 
     'options': ['⬜ Square', '🔺 Triangle', '⬤ Circle', '◼ Rectangle'], 'correct': 1},
    {'text': 'If you rotate the shape 90 degrees clockwise, what do you get?', 
     'options': ['↗ Up-Right', '↘ Down-Right', '↙ Down-Left', '↖ Up-Left'], 'correct': 1},
    {'text': 'Which figure is the mirror image of the given shape?', 
     'options': ['◀ Left Arrow', '▶ Right Arrow', '▲ Up Arrow', '▼ Down Arrow'], 'correct': 1},
    {'text': 'How many cubes are in this 3D structure?', 
     'options': ['4', '5', '6', '7'], 'correct': 1},
    {'text': 'Which of the following is a 3D shape?', 
     'options': ['Circle', 'Square', 'Cube', 'Triangle'], 'correct': 2},
    {'text': 'If a cube is cut into 8 smaller cubes, how many faces are painted?', 
     'options': ['24', '48', '36', '12'], 'correct': 0},
    {'text': 'Which pattern is the odd one out?', 
     'options': ['⬤ Solid Circle', '◯ Hollow Circle', '◉ Circle with Dot', '◎ Double Circle'], 'correct': 3},
    {'text': 'What is the next shape in the sequence: ⬤, ◼, ▲, ⬤, ◼, ?', 
     'options': ['⬤ Circle', '◼ Square', '▲ Triangle', '● Circle'], 'correct': 2}
]

IQ_MEMORY_QUESTIONS = [
    {'text': 'Remember this sequence: 3-7-2-9-5. What was the third number?', 
     'options': ['2', '7', '9', '5'], 'correct': 0},
    {'text': 'In the pattern: Red, Blue, Green, Yellow, Red, ? What comes next?', 
     'options': ['Blue', 'Green', 'Yellow', 'Red'], 'correct': 0},
    {'text': 'What was the first word in the sequence: Apple, Ball, Cat, Dog, Elephant?', 
     'options': ['Apple', 'Ball', 'Cat', 'Dog'], 'correct': 0},
    {'text': 'Remember: 8, 3, 6, 9, 2. What is the sum of the first and last numbers?', 
     'options': ['8', '9', '10', '11'], 'correct': 2},
    {'text': 'In the pattern: Circle, Square, Triangle, Circle, Square, ? What comes next?', 
     'options': ['Circle', 'Square', 'Triangle', 'Rectangle'], 'correct': 2},
    {'text': 'What was the 4th item in: Mouse, Keyboard, Monitor, CPU, Printer?', 
     'options': ['CPU', 'Printer', 'Monitor', 'Keyboard'], 'correct': 0},
    {'text': 'Remember: A, C, E, G, I. What comes next?', 
     'options': ['J', 'K', 'L', 'M'], 'correct': 1},
    {'text': 'In the sequence: 2, 4, 8, 16, ? What is the next number?', 
     'options': ['24', '32', '64', '128'], 'correct': 1}
]






