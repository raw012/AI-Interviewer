import os
import json
from groq import Groq

def get_client(api_key: str | None = None):
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment")
    return Groq(api_key=api_key)


def generate_followup(transcript: str):

    client = get_client()

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


def score_answer(
    question: str,
    transcript: str,
    topic: str = "",
    memory_context: str = "",
    api_key: str | None = None,
):

    client = get_client(api_key)

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
  "detected_topic": "Most specific knowledge area"
}}

Do not label a topic as a knowledge weakness merely because the candidate chose
not to answer. User relevance feedback will separately decide whether the
question matched the intended interview.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    import json
    try:
        return json.loads(response.choices[0].message.content.strip())
    except json.JSONDecodeError:
        # Fallback if Groq doesn't return valid JSON
        return {
            "score": 70,
            "strengths": "Answer provided",
            "improvements": "Could be more detailed",
            "weak_points": [],
            "strong_points": [],
            "detected_topic": topic,
        }


def update_interview_summary(
    existing_summary: str,
    question: str,
    answer: str,
    evaluation: dict,
    api_key: str | None = None,
) -> str:
    """Keep a compact, cumulative memory of the interview."""
    client = get_client(api_key)

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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content.strip()


def analyze_recording(
    transcript: str, memory_context: str = "", api_key: str | None = None
) -> dict:
    """Turn a real interview transcript into a structured retrospective."""
    client = get_client(api_key)
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
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    try:
        result = json.loads(response.choices[0].message.content.strip())
    except (json.JSONDecodeError, AttributeError) as exc:
        raise ValueError("The recording analysis did not return valid JSON") from exc
    if not isinstance(result.get("questions"), list) or not result["questions"]:
        raise ValueError("No interview questions could be identified in this recording")
    return result
