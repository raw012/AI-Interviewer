import os
from groq import Groq
from services.json_utils import clean_and_parse_json

def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment")
    return Groq(api_key=api_key)


def generate_followup(transcript: str):

    client = get_client()

    prompt = f"""
You are an AI interviewer conducting verbal/verbal-based interviews.

The candidate answered:

{transcript}

Generate ONE follow-up interview question.
IMPORTANT CONSTRAINTS:
- Only ask verbal/conversation questions - NO coding challenges, LeetCode problems, or whiteboarding
- NO questions asking to write code, pseudo-code, or technical syntax
- Ask about concepts, experiences, explanations, decisions, or examples
- Keep questions conversational and suitable for speaking
- Limit to 1-3 sentences
- If the answer is vague, ask for clarification
- If technical, ask to explain deeper concepts
- If behavioral, ask for specific examples

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
Score this interview answer from 0 to 100 and provide comprehensive feedback.

Answer:
{transcript}

Analyze the answer and respond ONLY with valid JSON, no other text. Follow this exact structure:
{{
  "score": 75,
  "key_concepts": "List 2-3 core knowledge points this answer demonstrates",
  "reference_answer": "Key points a reference answer should cover",
  "strengths": "Key strengths of this answer",
  "improvements": "Specific areas and gaps that could be improved",
  "suggestions": "Concrete suggestions to better answer this question next time"
}}

Be constructive and specific in your feedback.
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        return clean_and_parse_json(response.choices[0].message.content.strip())
    except (ValueError, Exception):
        # Fallback if Groq doesn't return valid JSON
        return {
            "score": 70,
            "key_concepts": "Answer-related concepts",
            "reference_answer": "Should have covered relevant technical aspects",
            "strengths": "Answer provided with relevant details",
            "improvements": "Could be more comprehensive and specific",
            "suggestions": "Include more concrete examples and technical depth"
        }