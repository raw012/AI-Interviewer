"""LLM prompt templates for all interview types."""


# ============= CODING INTERVIEW =============

CODING_SYSTEM = """You are a technical interviewer at a top tech company.
Your role is to select ONE appropriate LeetCode-style coding question and present it clearly.
Always return valid JSON only. No explanation outside the JSON."""


def coding_question_prompt(company: str, position: str, user_comments: str = "") -> str:
    """Generate a coding interview question prompt."""
    return f"""
Select the single most frequently asked LeetCode-style coding question for a {position} role at {company}.

Additional context from candidate: {user_comments if user_comments else "None"}

Return JSON only:
{{
  "question_title": "...",
  "question_focus": "Key concept being tested (e.g. BFS, Dynamic Programming)",
  "difficulty": "Easy | Medium | Hard",
  "problem_statement": "Full problem description with examples and constraints",
  "example_input": "...",
  "example_output": "...",
  "constraints": ["...", "..."]
}}
"""


# ============= RESUME-BASED INTERVIEW =============

RESUME_SYSTEM = """You are a senior technical interviewer conducting a resume-based interview.
Your goal is to probe deeply into the candidate's experience — 3 layers deep on each topic.
Layer 1: Ask about a specific project/technology from the resume.
Layer 2: Probe the technical implementation or decision-making behind it.
Layer 3: Challenge edge cases, alternatives, or deeper theory.
Always return valid JSON only."""


def resume_first_question_prompt(resume_text: str, job_description: str, user_comments: str = "") -> str:
    """Generate the first resume-based interview question."""
    return f"""
Resume:
{resume_text}

Job Description:
{job_description}

Additional candidate notes: {user_comments if user_comments else "None"}

Identify the most interesting technical item in this resume relevant to the job description.
Generate a Layer 1 opening question about it.

Return JSON only:
{{
  "question": "...",
  "question_focus": "What specific knowledge/skill this tests",
  "topic_area": "The resume item being probed (e.g. 'Thread management in Project X')",
  "depth_layer": 1
}}
"""


def resume_followup_prompt(resume_text: str, conversation_history: list, depth_layer: int, user_comments: str = "") -> str:
    """Generate a follow-up resume-based interview question."""
    history_str = "\n".join([f"Q: {q}\nA: {a}" for q, a in conversation_history])
    return f"""
Resume:
{resume_text}

Conversation so far:
{history_str}

Additional candidate notes: {user_comments if user_comments else "None"}

Generate a Layer {depth_layer} follow-up question that digs deeper into the candidate's last answer.
Layer 2 = probe implementation details or technical decisions.
Layer 3 = challenge with edge cases, failure modes, or alternative approaches.

Return JSON only:
{{
  "question": "...",
  "question_focus": "...",
  "depth_layer": {depth_layer}
}}
"""


# ============= TECHNICAL INTERVIEW =============

TECHNICAL_SYSTEM = """You are a senior technical interviewer testing computer science fundamentals.
Cover topics relevant to the job description and resume. Include: data structures, algorithms,
computer organization, OS concepts, networking, databases, or domain-specific topics.
Always return valid JSON only."""


def technical_question_prompt(resume_text: str, job_description: str, asked_topics: list, user_comments: str = "") -> str:
    """Generate a technical interview question."""
    return f"""
Resume:
{resume_text}

Job Description:
{job_description}

Topics already covered this session: {asked_topics}

Additional candidate notes: {user_comments if user_comments else "None"}

Select a technical concept question NOT yet covered. Prioritize topics mentioned in the JD or resume.

Return JSON only:
{{
  "question": "...",
  "question_focus": "Core CS concept being tested",
  "topic_category": "e.g. Operating Systems, Data Structures, Networking"
}}
"""


# ============= BEHAVIORAL INTERVIEW =============

BEHAVIORAL_SYSTEM = """You are an interviewer assessing behavioral competencies.
Dig 2 layers deep to verify the candidate's answer is genuine and specific.
Layer 1: The main behavioral question.
Layer 2: Ask for specific details, metrics, or how conflicts were resolved.
Always return valid JSON only."""


def behavioral_first_question_prompt(job_description: str, user_comments: str = "") -> str:
    """Generate the first behavioral interview question."""
    return f"""
Job Description:
{job_description}

Additional candidate notes: {user_comments if user_comments else "None"}

Identify the top behavioral competency required for this role (e.g. leadership, conflict resolution, ownership).
Generate a Layer 1 behavioral question using the STAR format expectation.

Return JSON only:
{{
  "question": "...",
  "question_focus": "Competency being assessed",
  "competency": "e.g. Cross-functional collaboration",
  "depth_layer": 1
}}
"""


def behavioral_followup_prompt(conversation_history: list, depth_layer: int) -> str:
    """Generate a follow-up behavioral interview question."""
    history_str = "\n".join([f"Q: {q}\nA: {a}" for q, a in conversation_history])
    return f"""
Conversation so far:
{history_str}

Generate a Layer {depth_layer} follow-up to verify the candidate's answer is genuine.
Layer 2: Ask for specific names, dates, metrics, or what the candidate personally did vs the team.

Return JSON only:
{{
  "question": "...",
  "question_focus": "...",
  "depth_layer": {depth_layer}
}}
"""


# ============= ANSWER EVALUATION =============

EVAL_SYSTEM = """You are a technical interviewer evaluating a candidate's answer.
Be fair but critical. Always return valid JSON only."""


def evaluate_answer_prompt(question: str, question_focus: str, user_answer: str, interview_type: str) -> str:
    """Generate an answer evaluation prompt."""
    return f"""
Interview type: {interview_type}
Question: {question}
Key concept being tested: {question_focus}
Candidate's answer: {user_answer}

Evaluate the answer and return JSON only:
{{
  "score": <integer 0-100>,
  "strengths": "What the candidate did well (1-2 sentences)",
  "improvement": "Specific, actionable feedback on what to improve (2-3 sentences)",
  "model_answer_hint": "A brief hint toward the ideal answer without giving it fully away"
}}
"""
