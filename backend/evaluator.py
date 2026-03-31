import os
from groq import Groq

def get_client():
    api_key = os.getenv("GROQ_API_KEY")
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


def score_answer(transcript: str):

    client = get_client()

    prompt = f"""
Score this interview answer from 0 to 100.

Answer:
{transcript}

Respond ONLY with valid JSON, no other text:
{{
  "score": 75,
  "strengths": "List 1-2 key strengths",
  "improvements": "List 1-2 areas for improvement"
}}
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
            "improvements": "Could be more detailed"
        }