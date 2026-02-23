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
Score this interview answer from 0 to 1.

Answer:
{transcript}

Return JSON format like:
{{
  "score": 0.75,
  "strengths": "...",
  "improvements": "..."
}}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content