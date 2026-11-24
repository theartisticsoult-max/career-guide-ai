"""Code-based career matching for psychometric profiles.

The match list and scores are decided here, not by the language model.
"""


def get_career_matches_from_psychometric(data):
    """Generate career matches based on psychometric profile"""
    interests = data.get('interests', {})
    aptitudes = data.get('aptitudes', {})

    top_interests = sorted(interests.items(), key=lambda x: x[1], reverse=True)[:3] if interests else []
    top_aptitudes = sorted(aptitudes.items(), key=lambda x: x[1], reverse=True)[:2] if aptitudes else []

    matches = []

    # Match based on interests and aptitudes
    if 'investigative' in [i[0] for i in top_interests]:
        matches.append({
            'title': 'Data Scientist / AI Engineer',
            'career_id': 'C049',
            'match': 92,
            'description': 'Combines analytical thinking with investigative interests for cutting-edge technology careers.',
            'reasons': ['Strong analytical aptitude', 'Investigative interest profile', 'High growth potential']
        })

        matches.append({
            'title': 'Research Scientist',
            'career_id': 'C280',
            'match': 88,
            'description': 'Research-focused career requiring analytical skills and scientific curiosity.',
            'reasons': ['Strong investigative interests', 'Analytical aptitude', 'Curiosity-driven work']
        })

    if 'artistic' in [i[0] for i in top_interests]:
        matches.append({
            'title': 'UX/UI Designer',
            'career_id': 'C169',
            'match': 85,
            'description': 'Creative role combining design with user psychology and technology.',
            'reasons': ['Artistic interests', 'Creative aptitude', 'User-focused work']
        })

        matches.append({
            'title': 'Graphic Designer',
            'career_id': 'C168',
            'match': 82,
            'description': 'Visual communication and creative design for various media.',
            'reasons': ['Strong artistic interests', 'Creative skills', 'Visual thinking']
        })

    if 'social' in [i[0] for i in top_interests]:
        matches.append({
            'title': 'Clinical Psychologist',
            'career_id': 'C007',
            'match': 88,
            'description': 'Helping profession requiring empathy and understanding of human behavior.',
            'reasons': ['Social interests', 'Interpersonal aptitude', 'Desire to help others']
        })

        matches.append({
            'title': 'Social Worker',
            'career_id': 'C256',
            'match': 85,
            'description': 'Community service and social welfare roles making a difference.',
            'reasons': ['Strong social interests', 'Empathetic nature', 'Community focus']
        })

    if 'enterprising' in [i[0] for i in top_interests]:
        matches.append({
            'title': 'Entrepreneur / Business Owner',
            'career_id': 'C074',
            'match': 90,
            'description': 'Build and lead your own business venture.',
            'reasons': ['Enterprising interests', 'Leadership potential', 'Risk-taking nature']
        })

        matches.append({
            'title': 'Management Consultant',
            'career_id': 'C072',
            'match': 86,
            'description': 'Help organizations improve and grow through strategic advice.',
            'reasons': ['Strategic thinking', 'Problem-solving skills', 'Business acumen']
        })

    if 'realistic' in [i[0] for i in top_interests]:
        matches.append({
            'title': 'Mechanical Engineer',
            'career_id': 'C033',
            'match': 84,
            'description': 'Design and build mechanical systems and components.',
            'reasons': ['Hands-on interests', 'Technical aptitude', 'Practical problem-solving']
        })

        matches.append({
            'title': 'Robotics Engineer',
            'career_id': 'C055',
            'match': 82,
            'description': 'Create and program robotic systems for various applications.',
            'reasons': ['Technical skills', 'Innovation focus', 'Building things']
        })

    if len(matches) < 3:
        matches.extend([
            {
                'title': 'Software Developer',
                'career_id': 'C016',
                'match': 80,
                'description': 'Create software applications and systems for various platforms.',
                'reasons': ['Problem-solving skills', 'Technical aptitude', 'Growing field']
            },
            {
                'title': 'Business Analyst',
                'career_id': 'C061',
                'match': 78,
                'description': 'Bridge business needs with technical solutions.',
                'reasons': ['Analytical skills', 'Communication abilities', 'Strategic thinking']
            }
        ])

    return matches[:5]
