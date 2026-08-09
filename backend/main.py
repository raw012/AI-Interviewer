from dotenv import load_dotenv
load_dotenv()
from evaluator import score_answer, update_interview_summary
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import uuid
import os

from speech import extract_audio, transcribe_audio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}
ALLOWED_DURATIONS = {30, 60}


def utc_now():
    return datetime.now(timezone.utc)


def seconds_remaining(session: dict) -> int:
    return max(0, int((session["deadline_at"] - utc_now()).total_seconds()))

@app.post("/start")
def start_interview(request: dict):
    """
    Start a new interview session
    Expected request body:
    {
        "job_description": "...",
        "resume": "...",  # optional
        "duration_minutes": 30  # optional; supported values are 30 and 60
    }
    """
    session_id = str(uuid.uuid4())
    duration_minutes = request.get("duration_minutes", 30)
    if duration_minutes not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail="Duration must be 30 or 60 minutes")

    started_at = utc_now()
    intro_q = "Could you please introduce yourself? Tell me about your background, experience, and why you're interested in this role."

    sessions[session_id] = {
        "job_description": request.get("job_description", ""),
        "resume": request.get("resume", ""),
        "duration_minutes": duration_minutes,
        "started_at": started_at,
        "deadline_at": started_at + timedelta(minutes=duration_minutes),
        "current_question_index": 0,
        "is_intro_done": False,  # Track if introduction has been answered
        "current_question": intro_q,
        "cumulative_summary": "",
        "history": []
    }

    return {
        "session_id": session_id,
        "question": intro_q,
        "question_number": 1,
        "duration_minutes": duration_minutes,
        "remaining_seconds": duration_minutes * 60
    }


def generate_initial_question(job_desc: str, resume: str = "") -> str:
    """Generate the first interview question - ask for introduction"""
    # Always ask for introduction as the first question
    return "Could you please introduce yourself? Tell me about your background, experience, and why you're interested in this role."


@app.post("/upload/{session_id}")
async def upload_answer(session_id: str, finish: bool = False, file: UploadFile = File(...)):
    try:
        if session_id not in sessions:
            return {"error": "Invalid session ID"}, 400

        session = sessions[session_id]
        os.makedirs("videos", exist_ok=True)

        video_path = f"videos/{uuid.uuid4()}.webm"

        with open(video_path, "wb") as f:
            f.write(await file.read())
        
        # Extract audio
        audio_path = extract_audio(video_path)
        # Convert to text
        transcript = transcribe_audio(audio_path)

        # Score the answer
        evaluation = score_answer(transcript)

        current_q_idx = session["current_question_index"]
        current_question = session["current_question"]

        # Store in history
        history_entry = {
            "question_number": current_q_idx + 1,
            "question": current_question,
            "transcript": transcript,
            "evaluation": evaluation,
            "video_path": video_path,
            "audio_path": audio_path
        }

        try:
            session["cumulative_summary"] = update_interview_summary(
                session["cumulative_summary"],
                current_question,
                transcript,
                evaluation,
            )
        except Exception as summary_error:
            print(f"Error updating interview summary: {summary_error}")
            fallback = (
                f"Q: {current_question}\n"
                f"Answer summary: {transcript[:500]}\n"
                f"Score: {evaluation.get('score', 0)}; "
                f"Improvement: {evaluation.get('improvements', '')}"
            )
            session["cumulative_summary"] = (
                session["cumulative_summary"] + "\n" + fallback
            )[-6000:]

        history_entry["qa_summary"] = session["cumulative_summary"]
        session["history"].append(history_entry)

        session["current_question_index"] += 1

        # Time expiry never interrupts an answer. It is checked only after the
        # current recording has been uploaded, transcribed, and evaluated.
        if finish or seconds_remaining(session) <= 0:
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": None,
                "question_number": session["current_question_index"],
                "remaining_seconds": 0,
                "interview_complete": True
            }

        # Check if we just finished the introduction
        if not session["is_intro_done"]:
            # Mark intro as done and generate first technical question
            session["is_intro_done"] = True
            first_tech_q = generate_new_question(
                session["job_description"],
                session["resume"],
                session["cumulative_summary"],
                session["history"],
            )
            session["current_question"] = first_tech_q
            
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": first_tech_q,
                "question_number": 2,
                "remaining_seconds": seconds_remaining(session),
                "interview_complete": False
            }

        next_q = generate_new_question(
            session["job_description"],
            session["resume"],
            session["cumulative_summary"],
            session["history"],
        )
        session["current_question"] = next_q

        return {
            "transcript": transcript,
            "evaluation": evaluation,
            "next_question": next_q,
            "question_number": session["current_question_index"] + 1,
            "remaining_seconds": seconds_remaining(session),
            "interview_complete": False
        }
    
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return {"error": f"Processing failed: {str(e)}"}, 500


def generate_new_question(
    job_desc: str,
    resume: str,
    cumulative_summary: str,
    history: list,
) -> str:
    """Generate the next interview question"""
    from evaluator import get_client
    
    client = get_client()
    
    recent_context = "No previous question and answer pairs."
    if history:
        recent_parts = []
        for item in history[-5:]:
            recent_parts.append(
                f"Question: {item['question']}\n"
                f"Candidate answer: {item['transcript']}"
            )
        recent_context = "\n\n".join(recent_parts)
    
    prompt = f"""
You are an AI technical interviewer. Generate ONE new technical interview question.

Job Description:
{job_desc}

Candidate resume (may be blank):
{resume}

Compact summary of the interview so far:
{cumulative_summary or "No interview summary yet."}

Five most recent full question and answer pairs:
{recent_context}

Ask a relevant technical question that:
- builds naturally on the candidate's demonstrated experience or gaps
- avoids repeating topics already covered
- Assesses skills needed for the role
- Is appropriately challenging

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
            "duration_minutes": session["duration_minutes"],
            "questions_answered": len(session["history"]),
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
        return {"error": f"Processing failed: {str(e)}"}, 500
