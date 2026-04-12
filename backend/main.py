from dotenv import load_dotenv
load_dotenv()
from evaluator import generate_followup, score_answer
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
import json
from datetime import datetime

from speech import extract_audio, transcribe_audio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

@app.post("/start")
def start_interview(request: dict):
    """
    Start a new interview session
    Expected request body:
    {
        "job_description": "...",
        "resume": "...",  # optional
        "num_questions": 5  # optional, default 5 (technical questions, intro is separate)
    }
    """
    session_id = str(uuid.uuid4())
    num_questions = request.get("num_questions", 5)

    sessions[session_id] = {
        "job_description": request.get("job_description", ""),
        "resume": request.get("resume", ""),
        "num_questions": num_questions,
        "current_question_index": 0,
        "is_intro_done": False,  # Track if introduction has been answered
        "history": [],  # List of {question, transcript, score, followup, video_path}
        "question_videos": {}  # Map of question_number -> video_path for playback
    }

    # Always start with introduction
    intro_q = "Could you please introduce yourself? Tell me about your background, experience, and why you're interested in this role."

    return {
        "session_id": session_id,
        "question": intro_q,
        "question_number": 1,
        "total_questions": num_questions + 1  # +1 for introduction
    }


def generate_initial_question(job_desc: str, resume: str = "") -> str:
    """Generate the first interview question - ask for introduction"""
    # Always ask for introduction as the first question
    return "Could you please introduce yourself? Tell me about your background, experience, and why you're interested in this role."


@app.post("/upload/{session_id}")
async def upload_answer(session_id: str, file: UploadFile = File(...)):
    try:
        if session_id not in sessions:
            return {"error": "Invalid session ID"}, 400

        session = sessions[session_id]
        os.makedirs("videos", exist_ok=True)
# Generate question ID for video filename based on question number
        question_num = session["current_question_index"] + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"question_{question_num}_{timestamp}.webm"
        video_path = os.path.join("videos", video_filename)

        with open(video_path, "wb") as f:
            f.write(await file.read())
        
        # Extract audio
        audio_path = extract_audio(video_path)
        # Convert to text
        transcript = transcribe_audio(audio_path)

        # Score the answer
        evaluation = score_answer(transcript)

        # Get current question from history or use placeholder
        current_q_idx = session["current_question_index"]
        if current_q_idx < len(session["history"]):
            current_question = session["history"][current_q_idx]["question"]
        else:
            current_question = "Interview Question"

        # Store in history
        history_entry = {
            "question_number": question_num,
            "question": current_question,
            "transcript": transcript,
            "evaluation": evaluation,
            "video_path": video_path,
            "audio_path": audio_path
        }
        session["history"].append(history_entry)
        
        # Map question number to video path for playback
        session["question_videos"][question_num] = video_path

        session["current_question_index"] += 1

        # Check if we just finished the introduction
        if not session["is_intro_done"]:
            # Mark intro as done and generate first technical question
            session["is_intro_done"] = True
            first_tech_q = generate_new_question(
                session["job_description"],
                session["history"],
                session["num_questions"]
            )
            
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": first_tech_q,
                "question_number": 2,  # First technical question is Q2 overall
                "total_questions": session["num_questions"] + 1,
                "interview_complete": False
            }

        # Decide: generate follow-up or next question (for technical questions)
        should_continue = session["current_question_index"] < (session["num_questions"] + 1)
        
        if should_continue:
            # Generate follow-up or new question (50/50 for variety)
            import random
            if random.random() < 0.5 and len(transcript) > 10:
                # Follow-up on current topic
                next_q = generate_followup(transcript)
            else:
                # New question
                next_q = generate_new_question(
                    session["job_description"],
                    session["history"],
                    session["num_questions"]
                )
            
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": next_q,
                "question_number": session["current_question_index"] + 1,
                "total_questions": session["num_questions"] + 1,
                "interview_complete": False
            }
        else:
            # Interview complete
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": None,
                "question_number": session["current_question_index"],
                "total_questions": session["num_questions"] + 1,
                "interview_complete": True
            }
    
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return {"error": f"Processing failed: {str(e)}"}, 500


def generate_new_question(job_desc: str, history: list, num_questions: int) -> str:
    """Generate the next interview question"""
    from evaluator import get_client
    
    client = get_client()
    
    previous_q_count = len(history)
    
    history_context = ""
    if history:
        history_context = "\nPrevious questions asked:\n"
        for item in history[-2:]:  # Last 2 questions for context
            history_context += f"- {item['question']}\n"
    
    prompt = f"""
You are an AI technical interviewer. Generate ONE new interview question.
This is question {previous_q_count + 1} out of {num_questions}.

Job Description:
{job_desc}
{history_context}

IMPORTANT - Only ask VERBAL QUESTIONS, NO CODING:
- Ask about concepts, experience, decisions, and examples only
- NO coding challenges, LeetCode problems, or whiteboarding tasks
- NO questions asking to write code, pseudo-code, or algorithms
- NO "design a system" questions that require code
- Keep it conversational - suitable for voice answers
- Limit to 1-3 sentences maximum
- Assess skills needed for the role through conversation

Only output the question, nothing else.
"""
    
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
    )
    
    return response.choices[0].message.content.strip()


@app.get("/summary/{session_id}")
def get_interview_summary(session_id: str):
    """Get complete interview summary with all Q&A and scores"""
    try:
        if session_id not in sessions:
            return {"error": "Invalid session ID"}, 400
        
        session = sessions[session_id]
        
        if not session["history"]:
            return {"error": "No answers recorded yet"}, 400
        
        # Calculate overall score
        scores = [h["evaluation"].get("score", 0) for h in session["history"]]
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Build summary
        summary = {
            "session_id": session_id,
            "num_questions": session["num_questions"],
            "overall_score": round(overall_score, 1),
            "interview_history": [
                {
                    "question_number": h["question_number"],
                    "question": h["question"],
                    "transcript": h["transcript"],
                    "score": h["evaluation"].get("score", 0),
                    "strengths": h["evaluation"].get("strengths", ""),
                    "improvements": h["evaluation"].get("improvements", ""),
                    "video_path": h["video_path"]
                }
                for h in session["history"]
            ]
        }
        
        # Generate encouraging message
        if overall_score >= 80:
            message = "Excellent performance! You demonstrated strong technical knowledge and communication skills."
        elif overall_score >= 70:
            message = "Good job! You answered most questions well. Keep practicing those edge cases."
        elif overall_score >= 60:
            message = "Solid effort! Focus on the suggested improvements and you'll be interview-ready soon."
        else:
            message = "Keep practicing! Each interview helps you improve. Review the suggestions and try again."
        
        summary["encouraging_message"] = message
        
        return summary
    
    except Exception as e:
        print(f"Error generating summary: {str(e)}")
        return {"error": f"Summary generation failed: {str(e)}"}, 500


@app.get("/playback/{session_id}/{question_number}")
def get_question_playback(session_id: str, question_number: int):
    """Get video playback data for a specific question"""
    try:
        if session_id not in sessions:
            return {"error": "Invalid session ID"}, 400
        
        session = sessions[session_id]
        
        # Find the question in history
        question_data = None
        for h in session["history"]:
            if h["question_number"] == question_number:
                question_data = h
                break
        
        if not question_data:
            return {"error": f"Question {question_number} not found"}, 404
        
        # Return playback data
        return {
            "question_number": question_number,
            "question": question_data["question"],
            "transcript": question_data["transcript"],
            "video_path": question_data["video_path"],
            "evaluation": question_data["evaluation"]
        }
    
    except Exception as e:
        print(f"Error retrieving playback: {str(e)}")
        return {"error": f"Playback retrieval failed: {str(e)}"}, 500