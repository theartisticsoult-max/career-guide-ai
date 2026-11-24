# chatbot_service.py
"""
Career Guide AI - Chatbot Service
Integrates Groq API with conversational context, secure environment variable configuration,
and robust fallback to domain career knowledge.
"""

import os
import re
import logging
from typing import List, Dict, Any, Optional

from app.services.llm_response import parse_explanation

logger = logging.getLogger(__name__)

# Default Groq model - high capability, fast, cost-effective
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are an expert AI Career Guidance Counselor for Career Guide AI.
You only write explanations and roadmaps. Career ranking, match scores and career
selection are computed by application code and must never be invented or reordered by you.

Respond with a single valid JSON object and no other text:
{"answer": "<your Markdown explanation or roadmap>"}

Guidelines:
1. Put the entire Markdown answer in the "answer" field (headers, bullet points, bold text).
2. When answering about in-demand skills, categorize them clearly (e.g., Core Programming, Cloud & DevOps, AI/ML, Soft Skills) and explain why they matter.
3. When comparing roles (e.g., AI Engineer vs Data Scientist), clearly highlight: Core Purpose, Key Responsibilities, Required Tech Stack, Math/Stats vs Engineering focus, and Typical Career Trajectory.
4. When detailing career roadmaps (e.g., How to become a backend engineer), break the journey down into logical phases: Foundations, Core Technologies, Databases & APIs, Architecture & System Design, and Projects/Certifications.
5. Provide realistic salary expectations and top recruiters when relevant.
6. Maintain a helpful, empathetic, professional, and motivating tone.
7. Maintain awareness of the conversation context and refer back to previously discussed topics when appropriate.
"""

def get_groq_client():
    """Instantiate Groq client using environment variable GROQ_API_KEY."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or not api_key.strip() or api_key.strip() == "your_groq_api_key_here":
        return None
    
    try:
        from groq import Groq
        return Groq(api_key=api_key.strip())
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None

def build_messages_payload(message: str, history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
    """Build messages payload with system prompt, sanitized conversation history, and current message."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    if history and isinstance(history, list):
        # Keep last 8 turns for balanced context and token efficiency
        sanitized_history = []
        for turn in history[-8:]:
            if isinstance(turn, dict):
                role = turn.get("role")
                content = turn.get("content")
                if role in ("user", "assistant") and content and isinstance(content, str):
                    sanitized_history.append({"role": role, "content": content.strip()})
        
        messages.extend(sanitized_history)
    
    # Ensure current message is added if not already the final item
    if not messages or messages[-1].get("content") != message:
        messages.append({"role": "user", "content": message.strip()})
        
    return messages

def call_groq_api(message: str, history: Optional[List[Dict[str, str]]] = None) -> Optional[str]:
    """Call Groq API with conversation context."""
    client = get_groq_client()
    if not client:
        return None
    
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip() or DEFAULT_GROQ_MODEL
    messages = build_messages_payload(message, history)
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
            top_p=0.95
        )
        if completion and completion.choices and len(completion.choices) > 0:
            content = completion.choices[0].message.content
            if content and content.strip():
                return content.strip()
    except Exception as e:
        logger.warning(f"Groq API call failed: {e}. Falling back to domain knowledge base.")
        return None
    
    return None

def get_intelligent_fallback_response(message: str, career_df=None) -> str:
    """
    Intelligent domain-specific fallback for career queries when Groq API key is absent or unreachable.
    Provides detailed, high-value guidance for common queries and queries in the career dataset.
    """
    msg_lower = message.lower().strip()
    
    # 1. Greetings
    if re.search(r'\b(hello|hi|hey|greetings|namaste)\b', msg_lower) and len(msg_lower.split()) <= 4:
        return (
            "👋 **Hello! Welcome to Career Guide AI!**\n\n"
            "I am your AI Career Guidance Assistant. I can help you with:\n"
            "• **Career Roadmaps & Pathways** (e.g., How to become a backend engineer)\n"
            "• **In-Demand Skills & Technologies** (e.g., Skills for cloud computing, AI, or data)\n"
            "• **Role Comparisons** (e.g., AI Engineer vs Data Scientist)\n"
            "• **Student Guidance** (e.g., Best careers for Computer Science students)\n"
            "• **Salaries, Education & Recruiters** across hundreds of career profiles\n\n"
            "What career path or question would you like to explore today?"
        )
    
    # 2. What skills are most in demand?
    if ('skill' in msg_lower and any(w in msg_lower for w in ['demand', 'most in demand', 'trending', 'future', 'top'])) or \
       msg_lower in ['what skills are most in demand?', 'what skills are in demand?']:
        return (
            "🔥 **Top Most In-Demand Skills in the Current Job Market:**\n\n"
            "### 1. Artificial Intelligence & Machine Learning\n"
            "• **Core Skills:** Python, PyTorch, TensorFlow, Hugging Face, Transformers.\n"
            "• **Generative AI:** LLM fine-tuning, Prompt Engineering, RAG (Retrieval-Augmented Generation), LangChain, Vector Databases.\n\n"
            "### 2. Cloud Computing & DevOps\n"
            "• **Cloud Providers:** AWS (Amazon Web Services), Microsoft Azure, Google Cloud (GCP).\n"
            "• **Infrastructure & Containers:** Docker, Kubernetes, Terraform (IaC), CI/CD pipelines (GitHub Actions, GitLab CI).\n\n"
            "### 3. Backend & Full-Stack Development\n"
            "• **Languages:** Python, Java, Go, TypeScript/JavaScript, C#.\n"
            "• **Data & APIs:** RESTful APIs, GraphQL, PostgreSQL, MongoDB, Redis, Microservices architecture.\n\n"
            "### 4. Data Engineering & Analytics\n"
            "• **Data Stack:** Advanced SQL, Apache Spark, Snowflake, dbt, Apache Kafka, Power BI / Tableau.\n\n"
            "### 5. Cybersecurity\n"
            "• **Focus Areas:** Network Security, Identity & Access Management (IAM), Cloud Security, Ethical Hacking, SOC Operations.\n\n"
            "### 6. Essential Soft Skills\n"
            "• Problem-solving, cross-functional communication, adaptability, and systems thinking.\n\n"
            "💡 *Would you like a specialized learning roadmap for any of these skill areas?*"
        )
    
    # 3. How do I become a backend engineer?
    if ('backend' in msg_lower and any(w in msg_lower for w in ['become', 'how do i', 'how to', 'roadmap', 'learn', 'engineer', 'developer'])):
        return (
            "🚀 **Complete Step-by-Step Roadmap to Becoming a Backend Engineer:**\n\n"
            "### Step 1: Master a Core Backend Language\n"
            "• Choose one primary language: **Python** (FastAPI/Django), **Go** (Golang), **Java** (Spring Boot), or **Node.js/TypeScript** (Express/NestJS).\n"
            "• Learn OOP, asynchronous programming, concurrency, and memory management.\n\n"
            "### Step 2: Understand Data Structures & Algorithms (DSA)\n"
            "• Arrays, Hash Maps, Linked Lists, Trees, Graphs, Sorting, and Searching.\n"
            "• Practice time & space complexity analysis (Big-O notation).\n\n"
            "### Step 3: Master Databases & Data Modeling\n"
            "• **Relational (SQL):** PostgreSQL or MySQL — schema design, indexing, transactions, ACID properties.\n"
            "• **NoSQL & Caching:** Redis (caching/sessions), MongoDB (document storage).\n\n"
            "### Step 4: API Design & Architecture\n"
            "• Build RESTful APIs, understand HTTP methods/status codes, authentication (JWT, OAuth 2.0).\n"
            "• Explore WebSockets for real-time data and GraphQL.\n"
            "• Understand Monolithic vs Microservices architecture.\n\n"
            "### Step 5: System Design & Scalability\n"
            "• Load balancing, message queues (RabbitMQ, Apache Kafka), caching strategies, and database sharding.\n\n"
            "### Step 6: DevOps & Deployment Basics\n"
            "• Git version control, Docker containerization, CI/CD pipelines, and deploying to cloud platforms (AWS, Render, GCP).\n\n"
            "💼 **Recommended Projects to Build:**\n"
            "1. An E-commerce backend with authentication, cart management, and payment gateway integration.\n"
            "2. A scalable URL Shortener with Redis caching and rate-limiting.\n"
            "3. A real-time chat application backend using WebSockets."
        )
    
    # 4. Difference between AI engineer and data scientist
    if ('difference' in msg_lower or 'vs' in msg_lower or 'compare' in msg_lower) and \
       ('ai' in msg_lower or 'artificial intelligence' in msg_lower or 'machine learning' in msg_lower) and \
       ('data scientist' in msg_lower or 'data science' in msg_lower):
        return (
            "⚖️ **AI Engineer vs Data Scientist: Key Differences Explained:**\n\n"
            "| Dimension | AI Engineer | Data Scientist |\n"
            "| :--- | :--- | :--- |\n"
            "| **Primary Focus** | Engineering, deploying, and optimizing AI models in production systems. | Analyzing data, testing hypotheses, and deriving business insights. |\n"
            "| **Core Objective** | Build scalable, real-time AI software products (LLMs, vision, speech). | Answer business questions and uncover patterns using statistics & ML. |\n"
            "| **Daily Tasks** | API integration, model optimization, RAG pipelines, model serving, latency reduction. | Data cleaning, exploratory data analysis (EDA), feature engineering, statistical modeling. |\n"
            "| **Skillset** | Strong Software Engineering (Python, C++, Docker, Kubernetes, MLOps, APIs). | Strong Statistics, Mathematics, Econometrics, Experimental Design (A/B testing). |\n"
            "| **Key Tools** | PyTorch, ONNX, TensorRT, LangChain, vLLM, Docker, Cloud AI APIs. | Python/R, Pandas, NumPy, Scikit-Learn, SQL, Tableau, Jupyter. |\n"
            "| **Deliverables** | Deployed AI services, low-latency microservices, fine-tuned model endpoints. | Executive dashboards, analytical reports, predictive ML prototypes. |\n\n"
            "🎯 **Which should you choose?**\n"
            "• Choose **AI Engineering** if you love software engineering, system architecture, building tools, and deploying working software.\n"
            "• Choose **Data Science** if you love mathematics, business strategy, finding hidden patterns in data, and presenting insights to stakeholders."
        )
    
    # 5. Which careers suit a computer science student?
    if ('computer science' in msg_lower or 'cs student' in msg_lower or 'cse' in msg_lower) and \
       any(w in msg_lower for w in ['career', 'suit', 'job', 'path', 'option', 'recommend']):
        return (
            "🎓 **Top Career Paths for Computer Science Students:**\n\n"
            "### 1. Software Development / Engineering\n"
            "• **Roles:** Frontend Developer, Backend Engineer, Full-Stack Developer, Mobile App Developer (Flutter/React Native/iOS/Android).\n"
            "• **Why it suits CS:** Directly applies programming paradigms, algorithms, and system design learned in university.\n\n"
            "### 2. Artificial Intelligence & Machine Learning\n"
            "• **Roles:** AI/ML Engineer, Data Scientist, NLP Engineer, Computer Vision Specialist.\n"
            "• **Why it suits CS:** Leverages linear algebra, discrete math, probability, and advanced Python/C++ skills.\n\n"
            "### 3. Cloud & DevOps Engineering\n"
            "• **Roles:** Cloud Architect, Site Reliability Engineer (SRE), Platform Engineer.\n"
            "• **Why it suits CS:** Deep focus on distributed systems, operating systems, networking, and virtualization.\n\n"
            "### 4. Cybersecurity & Information Security\n"
            "• **Roles:** Security Analyst, Penetration Tester, Application Security Engineer.\n"
            "• **Why it suits CS:** Utilizes computer networks, cryptography, operating systems, and reverse engineering.\n\n"
            "### 5. Data Engineering & Big Data\n"
            "• **Roles:** Data Engineer, Database Administrator, BI Developer.\n"
            "• **Why it suits CS:** Focuses on DBMS, distributed databases, SQL, and data pipeline scalability.\n\n"
            "### 6. Product & Technical Management\n"
            "• **Roles:** Technical Product Manager (TPM), Associate Product Manager (APM).\n"
            "• **Why it suits CS:** Combines technical understanding with business strategy and user empathy."
        )
    
    # 6. What skills should I learn for cloud computing?
    if 'cloud' in msg_lower and ('skill' in msg_lower or 'learn' in msg_lower or 'become' in msg_lower or 'start' in msg_lower):
        return (
            "☁️ **Essential Skills to Learn for Cloud Computing:**\n\n"
            "### 1. Master at least One Major Cloud Platform\n"
            "• **AWS (Amazon Web Services):** EC2, S3, Lambda, VPC, RDS, IAM (Cert: AWS Certified Solutions Architect).\n"
            "• *Or* **Microsoft Azure:** Azure VMs, Blob Storage, App Services, Entra ID (Cert: Azure AZ-104 / AZ-900).\n"
            "• *Or* **Google Cloud (GCP):** Compute Engine, Cloud Storage, BigQuery, GKE.\n\n"
            "### 2. Operating Systems & Networking Fundamentals\n"
            "• **Linux Essentials:** Command line navigation, shell scripting (Bash), permissions, package managers, SSH.\n"
            "• **Networking:** IP addressing, Subnets, DNS, TCP/IP, OSI model, VPNs, Firewalls, Load Balancers.\n\n"
            "### 3. Containerization & Orchestration\n"
            "• **Docker:** Creating Dockerfiles, building images, managing multi-container setups with Docker Compose.\n"
            "• **Kubernetes (K8s):** Pods, Deployments, Services, ConfigMaps, Ingress controllers.\n\n"
            "### 4. Infrastructure as Code (IaC)\n"
            "• **Terraform:** Writing declarative configuration files to provision cloud resources automatically.\n"
            "• Cloud-native tools: AWS CloudFormation or Azure Bicep.\n\n"
            "### 5. CI/CD & Automation\n"
            "• Building automated pipelines using **GitHub Actions**, GitLab CI, or Jenkins to test and deploy cloud workloads.\n\n"
            "### 6. Cloud Security & Cost Optimization\n"
            "• Principle of least privilege (IAM), encryption at rest and in transit, FinOps (cost monitoring and budgets).\n\n"
            "🛠️ **Next Step:** Start by setting up the AWS Free Tier, deploy a containerized web application on EC2, and configure a custom domain with SSL."
        )
    
    # 7. Check if a specific career in career_df is mentioned
    if career_df is not None:
        try:
            for _, career in career_df.iterrows():
                career_name = str(career.get('Career_Name', '')).lower()
                if career_name and len(career_name) > 3 and career_name in msg_lower:
                    entry_sal = career.get('Entry_Salary_LPA', 'Varies')
                    mid_sal = career.get('Mid_Salary_LPA', 'Varies')
                    sr_sal = career.get('Senior_Salary_LPA', 'Varies')
                    return (
                        f"📌 **{career.get('Career_Name')}** ({career.get('Category', 'Career')})\n\n"
                        f"• 📚 **Minimum Education:** {career.get('Min_Education', 'Bachelor Degree')}\n"
                        f"• 🎓 **Preferred Stream:** {career.get('Preferred_Stream', 'Any')}\n"
                        f"• 📖 **Required Degree:** {career.get('Required_Degree', 'Relevant Degree')}\n"
                        f"• ⏱️ **Duration:** {career.get('Duration_Years', 4)} years\n\n"
                        f"💰 **Salary Structure (India):**\n"
                        f"  - Entry Level: **{entry_sal} LPA**\n"
                        f"  - Mid Level: **{mid_sal} LPA**\n"
                        f"  - Senior Level: **{sr_sal} LPA**\n\n"
                        f"🔧 **Key Technical Skills:** {career.get('Key_Technical_Skills', 'Not specified')}\n\n"
                        f"🤝 **Key Soft Skills:** {career.get('Key_Soft_Skills', 'Communication, Problem Solving')}\n\n"
                        f"🏢 **Top Recruiters:** {career.get('Top_Recruiters_India', 'Leading industry firms')}\n\n"
                        f"📈 **Job Outlook:** {career.get('Job_Outlook', 'Growing demand')}\n\n"
                        f"💡 *Would you like preparation tips or related careers for this role?*"
                    )
        except Exception as e:
            logger.error(f"Error checking career_df in fallback: {e}")

    # 8. Check for stream or category recommendations
    if any(word in msg_lower for word in ['recommend', 'suggest', 'options for', 'what careers']):
        if 'science' in msg_lower:
            return (
                "🔬 **Recommended Career Options for Science Students:**\n\n"
                "• **Data Scientist & AI Specialist:** High demand, requires analytical reasoning and programming.\n"
                "• **Software Engineer / Systems Architect:** Strong engineering prospects across global tech.\n"
                "• **Biomedical Engineer / Biotechnology Researcher:** Blends life sciences with tech and medical devices.\n"
                "• **Robotics & Automation Engineer:** Focus on mechatronics, sensors, and intelligent systems.\n"
                "• **Astrophysicist / Research Scientist:** Pure science track in research institutions.\n\n"
                "Which specific branch (Computer Science, Biology, Physics, or Chemistry) excites you most?"
            )
        elif 'commerce' in msg_lower:
            return (
                "💼 **Recommended Career Options for Commerce Students:**\n\n"
                "• **Chartered Accountant (CA):** High prestige, auditing, taxation, and corporate finance.\n"
                "• **Investment Banker / Financial Analyst:** Valuations, mergers, capital markets, and equity research.\n"
                "• **FinTech Product Specialist:** Combines financial acumen with technology products.\n"
                "• **Management Consultant:** Advising Fortune 500 companies on growth, efficiency, and strategy.\n\n"
                "Would you like details on exams like CA, CFA, or MBA?"
            )
        elif 'arts' in msg_lower or 'humanities' in msg_lower:
            return (
                "🎨 **Recommended Career Options for Arts & Humanities Students:**\n\n"
                "• **UI/UX Designer & Product Designer:** High salary, merges design thinking, human psychology, and tech.\n"
                "• **Corporate Communications & PR Specialist:** Strategic media relations and brand narrative.\n"
                "• **Civil Services (UPSC / State PSC):** Public administration and governance.\n"
                "• **Digital Content Strategist & Creative Director:** Media, publishing, and creative advertising.\n\n"
                "Which creative or strategic domain would you like to explore further?"
            )

    # 9. Generic helpful career response
    return (
        "💡 **Career Guidance Insight:**\n\n"
        "To help you navigate your career path effectively, here are key areas you can ask me about:\n\n"
        "• **Skills & Roadmaps:** 'What skills are most in demand?' or 'How do I become a backend engineer?'\n"
        "• **Role Comparisons:** 'What is the difference between AI engineer and data scientist?'\n"
        "• **Degrees & Education:** 'Which careers suit a computer science student?' or 'What should I do after 12th?'\n"
        "• **Specialized Fields:** 'What skills should I learn for cloud computing or cybersecurity?'\n\n"
        "Tell me more about your current education, skills, or target industry, and I will tailor a specific roadmap for you!"
    )

def get_chatbot_response(message: str, history: Optional[List[Dict[str, str]]] = None, career_df=None) -> str:
    """
    Main entry point for chatbot response generation:
    1. Attempts genuinely conversational Groq API integration using supported model (llama-3.3-70b-versatile).
    2. Maintains conversation context across multi-turn exchanges.
    3. Gracefully falls back to domain-informed career intelligence if API key is not configured or unavailable.
    """
    if not message or not message.strip():
        return "Please ask a question about careers, skills, education, or salaries!"

    # Attempt Groq API completion; only validated explanations are returned.
    groq_reply = call_groq_api(message, history)
    if groq_reply:
        explanation = parse_explanation(groq_reply)
        if explanation:
            return explanation

    # Fallback to intelligent domain-aware responses
    return get_intelligent_fallback_response(message, career_df=career_df)
