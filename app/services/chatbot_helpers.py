"""Static chat responses kept out of the route layer."""


def get_career_details_text(career):
    """Get detailed career information as text"""
    return f"""**{career['Career_Name']}** ({career['Category']})

📚 **Education:** {career['Min_Education']}
🎓 **Preferred Stream:** {career['Preferred_Stream']}
📖 **Required Degree:** {career['Required_Degree']}
⏱️ **Duration:** {career['Duration_Years']} years

💰 **Salary:**
   Entry Level: {career['Entry_Salary_LPA']} LPA
   Mid Level: {career['Mid_Salary_LPA']} LPA
   Senior Level: {career['Senior_Salary_LPA']} LPA

🔧 **Technical Skills:** {career['Key_Technical_Skills']}

🤝 **Soft Skills:** {career['Key_Soft_Skills']}

🏢 **Top Recruiters:** {career['Top_Recruiters_India']}

📈 **Job Outlook:** {career['Job_Outlook']}

Would you like to know about similar careers or compare this with others?"""


def get_default_response():
    """Default response"""
    return """I can help you with career information! You can ask me about:

**Career Discovery:**
• 'Recommend careers for science student'
• 'What are the highest paying careers?'
• 'Best careers for the future'

**Specific Careers:**
• 'Tell me about Data Scientist'
• 'How to become a doctor?'
• 'Software engineer salary'

**Career Information:**
• 'What skills are in demand?'
• 'Government jobs after graduation'
• 'Careers with good work-life balance'

What would you like to explore?"""
