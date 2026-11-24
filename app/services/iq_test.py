"""Non-LLM analysis for IQ test results."""


def generate_iq_summary(data):
    """Generate AI summary for IQ test results"""
    iq = data.get('iq_score', 100)
    scores = data.get('section_scores', {})

    summary = f"""
    Based on your IQ test results, here's a comprehensive analysis:
    
    **Overall Cognitive Ability:**
    Your IQ score of {iq} places you in the {get_percentile_range(iq)}. 
    
    **Strengths:**
    {get_strengths_analysis(scores)}
    
    **Areas for Development:**
    {get_development_analysis(scores)}
    
    **Career Implications:**
    {get_career_implications(iq, scores)}
    
    **Recommended Next Steps:**
    {get_recommended_steps(scores)}
    """

    return summary


def get_percentile_range(iq):
    if iq >= 130: return "top 2% of the population"
    if iq >= 115: return "top 16% of the population"
    if iq >= 100: return "top 50% of the population"
    if iq >= 85: return "bottom 16% of the population"
    return "bottom 2% of the population"


def get_strengths_analysis(scores):
    strengths = []
    if scores.get('logical', 0) >= 6:
        strengths.append("• **Logical Reasoning**: Excellent pattern recognition and analytical thinking")
    if scores.get('numerical', 0) >= 6:
        strengths.append("• **Numerical Ability**: Strong mathematical and quantitative skills")
    if scores.get('verbal', 0) >= 6:
        strengths.append("• **Verbal Comprehension**: Excellent vocabulary and language understanding")
    if scores.get('spatial', 0) >= 6:
        strengths.append("• **Spatial Awareness**: Great visualization and spatial reasoning")
    if scores.get('memory', 0) >= 6:
        strengths.append("• **Memory & Recall**: Strong memory retention and recall abilities")

    if strengths:
        return "\n".join(strengths)
    return "You have a balanced cognitive profile across all areas."


def get_development_analysis(scores):
    developments = []
    if scores.get('logical', 0) < 4:
        developments.append("• Practice puzzles, Sudoku, and brain teasers to improve logical reasoning")
    if scores.get('numerical', 0) < 4:
        developments.append("• Regular mental math practice can strengthen numerical abilities")
    if scores.get('verbal', 0) < 4:
        developments.append("• Reading widely and learning new vocabulary can enhance verbal skills")
    if scores.get('spatial', 0) < 4:
        developments.append("• Try 3D puzzles, drawing, and visualization exercises")
    if scores.get('memory', 0) < 4:
        developments.append("• Use mnemonic techniques and regular recall exercises")

    if developments:
        return "\n".join(developments)
    return "Continue challenging yourself with advanced materials in your areas of interest."


def get_career_implications(iq, scores):
    if iq >= 130:
        return "Your cognitive abilities are exceptional. Consider careers in research, data science, AI engineering, theoretical physics, or neurosurgery where complex problem-solving is key."
    elif iq >= 115:
        return "Your above-average cognitive abilities suit careers in software engineering, financial analysis, architecture, corporate law, or medicine."
    elif iq >= 100:
        return "Your cognitive abilities are well-suited for careers in business analysis, graphic design, education, project management, or marketing."
    else:
        return "Your cognitive profile aligns well with practical careers in skilled trades, sales, administration, customer service, or technical fields."


def get_recommended_steps(scores):
    steps = []
    if scores.get('logical', 0) < 5:
        steps.append("1. Dedicate 15 minutes daily to logic puzzles and brain games")
    if scores.get('numerical', 0) < 5:
        steps.append("2. Practice mental math and numerical reasoning exercises")
    if scores.get('verbal', 0) < 5:
        steps.append("3. Read challenging books and learn 5 new words daily")
    if scores.get('spatial', 0) < 5:
        steps.append("4. Try drawing, 3D modeling, or puzzle games")
    if scores.get('memory', 0) < 5:
        steps.append("5. Use memory techniques like the method of loci")

    if not steps:
        steps = ["1. Take advanced courses in your areas of interest",
                 "2. Consider mentoring others to deepen your understanding",
                 "3. Explore interdisciplinary subjects to broaden your skills"]

    return "\n".join(steps)
