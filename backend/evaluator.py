import os
import json
from providers import complete_text

def generate_followup(transcript: str, provider: str = "groq", api_key: str | None = None):
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("No API key configured")

    prompt = f"""
You are an AI interviewer.

The candidate answered:

{transcript}

Generate ONE follow-up interview question.
If the answer is vague, ask for clarification.
If technical, ask deeper.
If behavioral, ask for example.
Only output the question.
"""

    return complete_text(provider, api_key, prompt)


def score_answer(
    question: str,
    transcript: str,
    topic: str = "",
    memory_context: str = "",
    api_key: str | None = None,
    provider: str = "groq",
):
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("No API key configured")

    prompt = f"""
Score this interview answer from 0 to 100.

Interview topic:
{topic or "General technical interview"}

Question:
{question}

Answer:
{transcript}

Known candidate memory (use only for longitudinal comparison, never to lower a
score without evidence in this answer):
{memory_context or "No prior memory."}

Respond ONLY with valid JSON, no other text:
{{
  "score": 75,
  "strengths": "List 1-2 key strengths",
  "improvements": "List 1-2 areas for improvement",
  "weak_points": ["Specific knowledge gap evidenced by this answer"],
  "strong_points": ["Specific demonstrated strength"],
  "detected_topic": "Most specific knowledge area",
  "dimension_scores": {{
    "technical_depth": 75,
    "communication": 75,
    "structured_thinking": 75,
    "problem_solving": 75,
    "project_articulation": 75,
    "adaptability": 75
  }},
  "user_memories": [
    {{"kind": "expertise", "content": "Specific expertise demonstrated by this answer"}},
    {{"kind": "communication_pattern", "content": "Stable communication behavior evidenced here"}}
  ]
}}

Do not label a topic as a knowledge weakness merely because the candidate chose
not to answer. User relevance feedback will separately decide whether the
question matched the intended interview.
Score each profile dimension from 0 to 100 only when this answer provides
evidence. Omit dimensions that cannot reasonably be observed from this answer.
Only include durable user_memories supported by the answer. Allowed kinds are
expertise, communication_pattern, working_style, and preference. Return an
empty list when there is no durable personal signal.
"""

    import json
    try:
        return json.loads(complete_text(provider, api_key, prompt))
    except json.JSONDecodeError:
        # Fallback if Groq doesn't return valid JSON
        return {
            "score": 70,
            "strengths": "Answer provided",
            "improvements": "Could be more detailed",
            "weak_points": [],
            "strong_points": [],
            "detected_topic": topic,
            "dimension_scores": {},
            "user_memories": [],
        }


def update_interview_summary(
    existing_summary: str,
    question: str,
    answer: str,
    evaluation: dict,
    api_key: str | None = None,
    provider: str = "groq",
) -> str:
    """Keep a compact, cumulative memory of the interview."""
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("No API key configured")

    prompt = f"""
You maintain compact context for a long-running technical interview.

Existing interview summary:
{existing_summary or "No previous answers."}

Latest question:
{question}

Latest answer:
{answer}

Latest evaluation:
- Score: {evaluation.get("score", 0)}
- Strengths: {evaluation.get("strengths", "")}
- Improvements: {evaluation.get("improvements", "")}

Rewrite the cumulative interview summary so it captures:
- topics and skills already covered
- the candidate's demonstrated strengths
- recurring gaps or areas to probe
- important claims or examples worth remembering

Keep it concise (maximum 500 words). Do not reproduce the full transcript.
Only output the updated summary.
"""

    return complete_text(provider, api_key, prompt)


def analyze_recording(
    transcript: str, memory_context: str = "", api_key: str | None = None,
    provider: str = "groq",
) -> dict:
    """Turn a real interview transcript into a structured retrospective."""
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("No API key configured")
    prompt = f"""
You are an interview coach reviewing a transcript of a real interview.
The transcript may contain both interviewer and candidate speech and may not
include speaker labels. Infer question/answer boundaries conservatively.

Transcript:
{transcript}

Prior candidate memory (use only for longitudinal comparison):
{memory_context or "No prior memory."}

Return ONLY valid JSON with this shape:
{{
  "summary": "Concise overall retrospective",
  "questions": [
    {{
      "question": "Interviewer question",
      "answer": "Candidate answer or best reconstruction",
      "score": 0,
      "strengths": "Specific strengths",
      "improvements": "Specific improvements",
      "weak_points": ["Evidence-based knowledge or communication gap"],
      "strong_points": ["Evidence-based demonstrated strength"],
      "detected_topic": "Specific topic"
    }}
  ]
}}

Use scores from 0 to 100. Do not invent content that is absent. If a question
or answer is unclear, say so. Include at most 20 substantive Q&A pairs.
"""
    try:
        result = json.loads(complete_text(provider, api_key, prompt))
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("The recording analysis did not return valid JSON") from exc
    if not isinstance(result.get("questions"), list) or not result["questions"]:
        raise ValueError("No interview questions could be identified in this recording")
    return result
