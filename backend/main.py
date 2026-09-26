from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import os
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

from evaluator import analyze_recording, score_answer, update_interview_summary
from providers import PROVIDERS, complete_text, test_provider
from speech import extract_audio, transcribe_audio
from storage import (
    api_key_for_user,
    api_key_status,
    authenticate_user,
    cancel_interview,
    complete_interview,
    create_interview,
    create_user_topic,
    delete_api_key,
    delete_demo_profile,
    create_user,
    delete_resume,
    init_db,
    issue_token,
    list_interviews,
    list_memory_items,
    list_recording_reviews,
    list_user_topics,
    memory_context,
    profile_dimension_statistics,
    provider_settings,
    recent_questions,
    resume_for_user,
    save_answer,
    save_api_key,
    save_question_feedback,
    save_provider_settings,
    save_resume,
    seed_demo_profile,
    skill_statistics,
    update_interview_summary as persist_interview_summary,
    upsert_memory,
    user_for_token,
)


app = FastAPI(title="AI Interview Coach")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

sessions: dict[str, dict] = {}
ALLOWED_DURATIONS = {30, 60}
MAX_RESUME_BYTES = 20 * 1024 * 1024
MAX_RECORDING_BYTES = 200 * 1024 * 1024
MEDIA_SUFFIXES = {".webm", ".mp4", ".mov", ".mkv", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}

SPECIAL_TOPICS = [
    {
        "key": "java_oop",
        "name": "Java OOP",
        "description": "Encapsulation, inheritance, polymorphism, abstraction, SOLID, design patterns, and the Java object model",
    },
    {
        "key": "computer_networks",
        "name": "Computer Networks",
        "description": "TCP/IP, HTTP, DNS, congestion control, reliable transport, and network troubleshooting",
    },
    {
        "key": "operating_systems",
        "name": "Operating Systems",
        "description": "Processes, threads, scheduling, synchronization, memory, file systems, I/O, and deadlocks",
    },
    {
        "key": "machine_learning",
        "name": "Machine Learning",
        "description": "Supervised and unsupervised learning, feature engineering, evaluation, regularization, and production ML",
    },
    {
        "key": "data_structures_algorithms",
        "name": "Data Structures & Algorithms",
        "description": "Core data structures, complexity, algorithm design, trade-offs, and problem-solving communication",
    },
    {
        "key": "deep_learning",
        "name": "Deep Learning",
        "description": "Neural networks, optimization, CNNs, sequence models, transformers, training, and deployment",
    },
]
TOPIC_BY_KEY = {item["key"]: item for item in SPECIAL_TOPICS}


def topic_catalog(user_id: str) -> list[dict]:
    return [{**item, "custom": False} for item in SPECIAL_TOPICS] + list_user_topics(user_id)


def topic_for_user(user_id: str, key: str) -> dict | None:
    return next((item for item in topic_catalog(user_id) if item["key"] == key), None)


def resolved_api_key(user_id: str, provider: str = "groq") -> str:
    personal_key = api_key_for_user(user_id, provider)
    environment_key = os.getenv(f"{provider.upper()}_API_KEY", "").strip()
    key = personal_key or environment_key
    if not key or key == "paste_your_new_groq_api_key_here":
        raise HTTPException(
            status_code=400,
            detail=f"Configure a {PROVIDERS[provider]['name']} API key in API Settings",
        )
    return key


def provider_runtime(user_id: str, capability: str) -> tuple[str, str]:
    settings = provider_settings(user_id)
    provider = settings[
        "transcription_provider" if capability == "transcription" else "llm_provider"
    ]
    if provider not in PROVIDERS or not PROVIDERS[provider].get(capability if capability == "transcription" else "chat"):
        raise HTTPException(status_code=400, detail=f"Selected provider cannot perform {capability}")
    return provider, resolved_api_key(user_id, provider)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_remaining(session: dict) -> int:
    return max(0, int((session["deadline_at"] - utc_now()).total_seconds()))


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Please sign in")
    user = user_for_token(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again")
    return user


def token_response(user: dict) -> dict:
    return {"token": issue_token(user["id"]), "user": user}


def extract_resume_text(pdf: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to read this PDF resume") from exc


def owned_session(session_id: str, user_id: str) -> dict:
    session = sessions.get(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return session


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/auth/register")
def register(request: dict) -> dict:
    try:
        user = create_user(
            str(request.get("email", "")),
            str(request.get("password", "")),
            str(request.get("name", "")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return token_response(user)


@app.post("/auth/login")
def login(request: dict) -> dict:
    user = authenticate_user(
        str(request.get("email", "")), str(request.get("password", ""))
    )
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return token_response(user)


@app.get("/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return user


@app.get("/topics")
def topics(user: dict = Depends(current_user)) -> dict:
    return {"topics": topic_catalog(user["id"])}


@app.post("/topics")
def add_topic(request: dict, user: dict = Depends(current_user)) -> dict:
    try:
        return create_user_topic(
            user["id"], str(request.get("name", "")), str(request.get("description", ""))
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/resume/status")
def resume_status(user: dict = Depends(current_user)) -> dict:
    resume = resume_for_user(user["id"])
    if not resume:
        return {"has_resume": False}
    return {
        "has_resume": True,
        "filename": resume["filename"],
        "updated_at": resume["updated_at"],
    }


@app.post("/resume")
async def upload_resume(
    file: UploadFile = File(...), user: dict = Depends(current_user)
) -> dict:
    filename = os.path.basename(file.filename or "resume.pdf")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported")
    payload = await file.read()
    if not payload.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a PDF")
    if len(payload) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume must be 20 MB or smaller")
    text = extract_resume_text(payload)
    if not text:
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted. Please upload a text-based PDF",
        )
    save_resume(user["id"], filename, payload, text[:50_000])
    return {"ok": True, "filename": filename}


@app.delete("/resume")
def remove_resume(user: dict = Depends(current_user)) -> dict:
    return {"ok": delete_resume(user["id"])}


@app.get("/history")
def interview_history(user: dict = Depends(current_user)) -> dict:
    return {
        "interviews": list_interviews(user["id"]),
        "recording_reviews": list_recording_reviews(user["id"]),
    }


@app.get("/memory")
def learning_memory(user: dict = Depends(current_user)) -> dict:
    return {"items": list_memory_items(user["id"])}


@app.get("/dashboard")
def dashboard(user: dict = Depends(current_user)) -> dict:
    catalog = {item["key"]: item["name"] for item in topic_catalog(user["id"])}
    skills = skill_statistics(user["id"])
    for skill in skills:
        skill["name"] = catalog.get(skill["topic"], "General Interview" if skill["topic"] == "general" else skill["topic"].replace("_", " ").title())
    memories = list_memory_items(user["id"])
    interviews = list_interviews(user["id"])
    recording_reviews = list_recording_reviews(user["id"])
    return {
        "skills": skills,
        "profile": profile_dimension_statistics(user["id"]),
        "memories": memories,
        "interviews": interviews,
        "recording_reviews": recording_reviews,
        "summary": {
            "interviews": len(list_interviews(user["id"], 1000)),
            "recording_reviews": len(list_recording_reviews(user["id"], 1000)),
            "active_memories": len(memories),
            "weak_points": sum(1 for item in memories if item["kind"] == "weak_point"),
            "strong_points": sum(1 for item in memories if item["kind"] == "strong_point"),
        },
    }


@app.post("/profile/demo")
def add_demo_profile(user: dict = Depends(current_user)) -> dict:
    return {
        "inserted": seed_demo_profile(user["id"]),
        "profile": profile_dimension_statistics(user["id"]),
    }


@app.delete("/profile/demo")
def remove_demo_profile(user: dict = Depends(current_user)) -> dict:
    return {
        "deleted": delete_demo_profile(user["id"]),
        "profile": profile_dimension_statistics(user["id"]),
    }


@app.get("/settings/api-key")
def get_api_key_settings(user: dict = Depends(current_user)) -> dict:
    status = api_key_status(user["id"])
    environment_key = os.getenv("GROQ_API_KEY", "").strip()
    status["server_fallback_available"] = bool(
        environment_key and environment_key != "paste_your_new_groq_api_key_here"
    )
    return status


@app.get("/settings/providers")
def get_provider_settings(user: dict = Depends(current_user)) -> dict:
    active = provider_settings(user["id"])
    providers = []
    for key, metadata in PROVIDERS.items():
        status = api_key_status(user["id"], key)
        environment_key = os.getenv(f"{key.upper()}_API_KEY", "").strip()
        providers.append(
            {
                "key": key,
                **metadata,
                **status,
                "server_fallback_available": bool(environment_key),
            }
        )
    return {"providers": providers, **active}


@app.put("/settings/providers/{provider}/key")
def update_provider_key(
    provider: str, request: dict, user: dict = Depends(current_user)
) -> dict:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    api_key = str(request.get("api_key", "")).strip()
    if len(api_key) < 12:
        raise HTTPException(status_code=400, detail="Enter a valid API key")
    save_api_key(user["id"], provider, api_key)
    return api_key_status(user["id"], provider)


@app.post("/settings/providers/{provider}/test")
def test_provider_key(
    provider: str, request: dict, user: dict = Depends(current_user)
) -> dict:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    supplied = str(request.get("api_key", "")).strip()
    api_key = supplied or resolved_api_key(user["id"], provider)
    try:
        test_provider(provider, api_key)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"The {PROVIDERS[provider]['name']} key could not be verified"
        ) from exc
    return {"ok": True, "message": "Connection successful"}


@app.delete("/settings/providers/{provider}/key")
def remove_provider_key(provider: str, user: dict = Depends(current_user)) -> dict:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unsupported provider")
    return {"ok": delete_api_key(user["id"], provider)}


@app.put("/settings/providers/active")
def update_active_providers(
    request: dict, user: dict = Depends(current_user)
) -> dict:
    llm_provider = str(request.get("llm_provider", "groq"))
    transcription_provider = str(request.get("transcription_provider", "groq"))
    if llm_provider not in PROVIDERS or not PROVIDERS[llm_provider]["chat"]:
        raise HTTPException(status_code=400, detail="Invalid interview intelligence provider")
    if transcription_provider not in PROVIDERS or not PROVIDERS[transcription_provider]["transcription"]:
        raise HTTPException(status_code=400, detail="Invalid transcription provider")
    return save_provider_settings(user["id"], llm_provider, transcription_provider)


@app.put("/settings/api-key")
def update_api_key(request: dict, user: dict = Depends(current_user)) -> dict:
    api_key = str(request.get("api_key", "")).strip()
    if not api_key.startswith("gsk_") or len(api_key) < 20:
        raise HTTPException(status_code=400, detail="Enter a valid Groq API key")
    save_api_key(user["id"], "groq", api_key)
    return api_key_status(user["id"])


@app.post("/settings/api-key/test")
def test_api_key(request: dict, user: dict = Depends(current_user)) -> dict:
    supplied = str(request.get("api_key", "")).strip()
    api_key = supplied or resolved_api_key(user["id"])
    try:
        test_provider("groq", api_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The Groq API key could not be verified") from exc
    return {"ok": True, "message": "Connection successful"}


@app.delete("/settings/api-key")
def remove_api_key(user: dict = Depends(current_user)) -> dict:
    return {"ok": delete_api_key(user["id"], "groq")}


@app.post("/recording-review")
async def recording_review(
    file: UploadFile = File(...), user: dict = Depends(current_user)
) -> dict:
    filename = os.path.basename(file.filename or "interview.webm")
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in MEDIA_SUFFIXES:
        raise HTTPException(status_code=400, detail="Unsupported audio or video format")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="The recording is empty")
    if len(payload) > MAX_RECORDING_BYTES:
        raise HTTPException(status_code=413, detail="Recording must be 200 MB or smaller")

    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    media_path = os.path.join(uploads_dir, f"{uuid.uuid4()}{suffix}")
    with open(media_path, "wb") as output:
        output.write(payload)

    try:
        audio_path = media_path if suffix in AUDIO_SUFFIXES else extract_audio(media_path)
        transcription_provider, transcription_key = provider_runtime(user["id"], "transcription")
        llm_provider, llm_key = provider_runtime(user["id"], "llm")
        transcript = transcribe_audio(audio_path, transcription_key, transcription_provider)
        analysis = analyze_recording(
            transcript, memory_context(user["id"]), llm_key, llm_provider
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recording review failed: {exc}") from exc

    session_id = str(uuid.uuid4())
    now = utc_now()
    session = {
        "session_id": session_id,
        "user_id": user["id"],
        "job_description": "Imported real interview recording",
        "resume": "",
        "mode": "recording",
        "topic": "",
        "duration_minutes": 0,
        "started_at": now,
        "deadline_at": now,
        "current_question_index": 0,
        "cumulative_summary": str(analysis.get("summary", "")),
        "history": [],
        "is_intro_done": True,
    }
    create_interview(session)
    for index, item in enumerate(analysis["questions"][:20], start=1):
        evaluation = {
            "score": max(0, min(100, float(item.get("score", 0)))),
            "strengths": str(item.get("strengths", "")),
            "improvements": str(item.get("improvements", "")),
            "weak_points": item.get("weak_points", []),
            "strong_points": item.get("strong_points", []),
            "detected_topic": str(item.get("detected_topic", "")),
        }
        entry = {
            "question_number": index,
            "question": str(item.get("question", "Unclear question")),
            "transcript": str(item.get("answer", "Answer unclear in recording")),
            "evaluation": evaluation,
            "video_path": media_path,
            "audio_path": audio_path,
        }
        session["history"].append(entry)
        answer_id = save_answer(user["id"], session_id, entry, evaluation["detected_topic"])
        for point in evaluation["weak_points"]:
            upsert_memory(user["id"], "weak_point", evaluation["detected_topic"], str(point), answer_id)
        for point in evaluation["strong_points"]:
            upsert_memory(user["id"], "strong_point", evaluation["detected_topic"], str(point), answer_id)
    session["current_question_index"] = len(session["history"])
    persist_interview_summary(session_id, session["cumulative_summary"])
    sessions[session_id] = session
    overall_score = mark_session_complete(session)
    return summary_payload(session, overall_score, transcript=transcript)


@app.post("/start")
def start_interview(request: dict, user: dict = Depends(current_user)) -> dict:
    duration_minutes = int(request.get("duration_minutes", 30))
    if duration_minutes not in ALLOWED_DURATIONS:
        raise HTTPException(status_code=400, detail="Duration must be 30 or 60 minutes")

    mode = str(request.get("mode", "general"))
    topic = str(request.get("topic", ""))
    if mode not in {"general", "special"}:
        raise HTTPException(status_code=400, detail="Unsupported interview mode")
    selected_topic = topic_for_user(user["id"], topic) if mode == "special" else None
    if mode == "special" and not selected_topic:
        raise HTTPException(status_code=400, detail="Choose a supported training topic")

    stored_resume = resume_for_user(user["id"])
    resume_text = stored_resume["extracted_text"] if stored_resume else ""
    job_description = str(request.get("job_description", "")).strip()
    if mode == "general" and not job_description and not resume_text:
        raise HTTPException(
            status_code=400,
            detail="Add a job description or upload a resume before starting",
        )

    session_id = str(uuid.uuid4())
    started_at = utc_now()
    session = {
        "session_id": session_id,
        "user_id": user["id"],
        "job_description": job_description,
        "resume": resume_text,
        "mode": mode,
        "topic": topic,
        "topic_info": selected_topic or {},
        "duration_minutes": duration_minutes,
        "started_at": started_at,
        "deadline_at": started_at + timedelta(minutes=duration_minutes),
        "current_question_index": 0,
        "cumulative_summary": "",
        "history": [],
    }
    if mode == "special":
        first_question = generate_new_question(session)
        session["is_intro_done"] = True
    else:
        first_question = (
            "Could you please introduce yourself? Tell me about your background, "
            "experience, and why you're interested in this role."
        )
        session["is_intro_done"] = False

    session["current_question"] = first_question
    sessions[session_id] = session
    create_interview(session)

    return {
        "session_id": session_id,
        "question": first_question,
        "question_number": 1,
        "duration_minutes": duration_minutes,
        "remaining_seconds": duration_minutes * 60,
        "mode": mode,
        "topic": topic,
    }


@app.post("/cancel/{session_id}")
def cancel_active_interview(
    session_id: str, user: dict = Depends(current_user)
) -> dict:
    owned_session(session_id, user["id"])
    cancel_interview(session_id)
    sessions.pop(session_id, None)
    return {"ok": True}


@app.post("/upload/{session_id}")
async def upload_answer(
    session_id: str,
    finish: bool = False,
    file: UploadFile = File(...),
    user: dict = Depends(current_user),
) -> dict:
    session = owned_session(session_id, user["id"])
    os.makedirs("videos", exist_ok=True)
    video_path = f"videos/{uuid.uuid4()}.webm"

    try:
        with open(video_path, "wb") as output:
            output.write(await file.read())
        audio_path = extract_audio(video_path)
        transcription_provider, transcription_key = provider_runtime(user["id"], "transcription")
        llm_provider, llm_key = provider_runtime(user["id"], "llm")
        transcript = transcribe_audio(audio_path, transcription_key, transcription_provider)

        question = session["current_question"]
        cross_session_memory = memory_context(user["id"], session["topic"])
        evaluation = score_answer(
            question, transcript, session["topic"], cross_session_memory, llm_key,
            llm_provider,
        )

        question_number = session["current_question_index"] + 1
        entry = {
            "question_number": question_number,
            "question": question,
            "transcript": transcript,
            "evaluation": evaluation,
            "video_path": video_path,
            "audio_path": audio_path,
        }

        try:
            session["cumulative_summary"] = update_interview_summary(
                session["cumulative_summary"], question, transcript, evaluation,
                llm_key, llm_provider,
            )
        except Exception as summary_error:
            print(f"Error updating interview summary: {summary_error}")
            fallback = (
                f"Q: {question}\nAnswer summary: {transcript[:500]}\n"
                f"Score: {evaluation.get('score', 0)}; "
                f"Improvement: {evaluation.get('improvements', '')}"
            )
            session["cumulative_summary"] = (
                session["cumulative_summary"] + "\n" + fallback
            )[-6000:]

        session["history"].append(entry)
        session["current_question_index"] += 1
        answer_id = save_answer(user["id"], session_id, entry, session["topic"])
        persist_interview_summary(session_id, session["cumulative_summary"])

        detected_topic = str(evaluation.get("detected_topic") or session["topic"])
        for point in evaluation.get("weak_points", []):
            upsert_memory(user["id"], "weak_point", detected_topic, str(point), answer_id)
        for point in evaluation.get("strong_points", []):
            upsert_memory(user["id"], "strong_point", detected_topic, str(point), answer_id)
        for learned in evaluation.get("user_memories", []):
            if not isinstance(learned, dict):
                continue
            kind = str(learned.get("kind", ""))
            if kind in {"expertise", "communication_pattern", "working_style", "preference"}:
                upsert_memory(
                    user["id"], kind, detected_topic, str(learned.get("content", "")), answer_id
                )

        if finish or seconds_remaining(session) <= 0:
            mark_session_complete(session)
            return {
                "transcript": transcript,
                "evaluation": evaluation,
                "next_question": None,
                "question_number": session["current_question_index"],
                "remaining_seconds": 0,
                "interview_complete": True,
            }

        session["is_intro_done"] = True
        next_question = generate_new_question(session)
        session["current_question"] = next_question
        return {
            "transcript": transcript,
            "evaluation": evaluation,
            "next_question": next_question,
            "question_number": session["current_question_index"] + 1,
            "remaining_seconds": seconds_remaining(session),
            "interview_complete": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Error processing upload: {exc}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc


def generate_new_question(session: dict) -> str:
    topic_info = session.get("topic_info") or TOPIC_BY_KEY.get(session["topic"], {})
    recent_context = "No previous question and answer pairs in this interview."
    if session["history"]:
        recent_context = "\n\n".join(
            f"Question: {item['question']}\nCandidate answer: {item['transcript']}"
            for item in session["history"][-5:]
        )

    long_term_memory = memory_context(session["user_id"], session["topic"])
    asked_before = recent_questions(session["user_id"], session["topic"], 20)
    mode_instruction = (
        f"This is focused training for {topic_info.get('name')}. Stay within: "
        f"{topic_info.get('description')}."
        if session["mode"] == "special"
        else "This is a role-focused technical interview based on the job and resume."
    )

    prompt = f"""
You are an AI technical interviewer. Generate ONE verbal interview question.

Mode:
{mode_instruction}

Job Description:
{session['job_description'] or 'Not provided.'}

Candidate resume:
{session['resume'] or 'Not provided.'}

Compact summary of the current interview:
{session['cumulative_summary'] or 'No current-session summary yet.'}

Verified cross-interview memory:
{long_term_memory}

Five most recent full Q&A pairs in this interview:
{recent_context}

Questions recently asked in earlier interviews (do not repeat or lightly rephrase):
{chr(10).join(f'- {question}' for question in asked_before) or '- None'}

Requirements:
- Prefer due or repeatedly observed weak points when they match the selected topic or role.
- Do not ask a question merely because it appeared in memory; it must match this interview.
- Do not repeat earlier questions or test the same narrow fact repeatedly.
- Ask about concepts, experience, decisions, trade-offs, debugging, or examples.
- No coding exercise, pseudo-code, or whiteboard task.
- Keep it conversational and answerable aloud in 1-3 sentences.
- Only output the question.
"""
    provider, api_key = provider_runtime(session["user_id"], "llm")
    return complete_text(provider, api_key, prompt)


def mark_session_complete(session: dict) -> float:
    scores = [item["evaluation"].get("score", 0) for item in session["history"]]
    overall = round(sum(scores) / len(scores), 1) if scores else 0
    complete_interview(session["session_id"], overall)
    return overall


def summary_payload(session: dict, overall_score: float, transcript: str = "") -> dict:
    payload = {
        "session_id": session["session_id"],
        "duration_minutes": session["duration_minutes"],
        "questions_answered": len(session["history"]),
        "overall_score": overall_score,
        "mode": session["mode"],
        "topic": session["topic"],
        "interview_history": [
            {
                "question_number": item["question_number"],
                "question": item["question"],
                "transcript": item["transcript"],
                "score": item["evaluation"].get("score", 0),
                "strengths": item["evaluation"].get("strengths", ""),
                "improvements": item["evaluation"].get("improvements", ""),
                "relevance": "pending",
                "issue_type": "",
            }
            for item in session["history"]
        ],
        "encouraging_message": encouragement(overall_score),
        "summary": session.get("cumulative_summary", ""),
    }
    if transcript:
        payload["full_transcript"] = transcript
    return payload


@app.get("/summary/{session_id}")
def get_interview_summary(
    session_id: str, user: dict = Depends(current_user)
) -> dict:
    session = owned_session(session_id, user["id"])
    if not session["history"]:
        raise HTTPException(status_code=400, detail="No answers recorded yet")

    overall_score = mark_session_complete(session)
    return summary_payload(session, overall_score)


@app.post("/feedback/{session_id}/{question_number}")
def question_feedback(
    session_id: str,
    question_number: int,
    request: dict,
    user: dict = Depends(current_user),
) -> dict:
    owned_session(session_id, user["id"])
    relevance = str(request.get("relevance", ""))
    issue_type = str(request.get("issue_type", ""))
    if relevance not in {"expected", "mismatch"}:
        raise HTTPException(status_code=400, detail="Choose expected or mismatch")
    if issue_type not in {"", "knowledge_gap", "question_mismatch", "other"}:
        raise HTTPException(status_code=400, detail="Unsupported feedback type")
    try:
        save_question_feedback(
            user["id"], session_id, question_number, relevance, issue_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


def encouragement(score: float) -> str:
    if score >= 80:
        return "Excellent performance. You demonstrated strong knowledge and communication."
    if score >= 70:
        return "Good job. Review the gaps below and keep building depth."
    if score >= 60:
        return "Solid effort. Use the improvement notes to guide the next focused session."
    return "Keep practicing. Your feedback will help distinguish knowledge gaps from mismatched questions."
