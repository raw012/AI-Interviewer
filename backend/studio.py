"""Studio API: intake, live interviews, coaching reports, memory and account management."""

from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile

from auth_google import client_id as google_client_id
from auth_google import verify_id_token
from deps import current_user, optional_voice_key, provider_runtime, server_fallback_available
from engine import build_plan, coach_hint, final_report, new_state, opening, retry_answer, take_turn
from intake import apply_answers, digest_resume, parse_goal, role_brief
from knowledge import COMPANIES, COMPETENCY_LABELS, LEVELS, PERSONAS, PRESSURE_STYLES, ROLE_FAMILIES, ROUNDS
from llm import ModelError
from memory import add_memory, clear_memory, delete_memory, edit_memory, expire_candidates, focus_competencies, list_memory
from providers import transcribe_file
from question_seed import QUESTIONS
from storage import connection, issue_token
from studio_store import (
    account_info,
    create_studio_interview,
    delete_account,
    delete_studio_interview,
    export_user_data,
    get_profile,
    google_user,
    list_studio_interviews,
    load_studio_interview,
    question_bank_stats,
    revoke_tokens,
    save_profile,
    save_studio_state,
    set_password,
    update_name,
    upsert_questions,
    usage_summary,
)
from voice import available_voices, resolve_voice, speak

router = APIRouter()
MAX_AUDIO_BYTES = 25 * 1024 * 1024
ALLOWED_MINUTES = {15, 30, 45, 60}


def init_studio_data() -> None:
    upsert_questions(QUESTIONS, origin="seed")


def _interview(session_id: str, user_id: str) -> dict:
    interview = load_studio_interview(session_id, user_id)
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    return interview


def _model_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail="The AI model didn't respond. Check your provider key in Settings, then try again.")


# ---------------------------------------------------------------- public config


@router.get("/studio/config")
def config() -> dict:
    return {
        "google_client_id": google_client_id(),
        "personas": [
            {"key": k, "name": v["name"], "title": v["title"], "style": v["style"], "look": v["look"], "voices": v["voices"]}
            for k, v in PERSONAS.items()
        ],
        "pressures": [{"key": k, "description": v} for k, v in PRESSURE_STYLES.items()],
        "roles": [{"key": k, "label": v["label"]} for k, v in ROLE_FAMILIES.items()],
        "levels": [{"key": k, "label": v["label"]} for k, v in LEVELS.items()],
        "rounds": [{"key": k, "label": v["label"], "minutes": v["minutes"], "assesses": v["assesses"]} for k, v in ROUNDS.items()],
        "companies": [{"key": k, "label": v["label"]} for k, v in COMPANIES.items()],
        "competencies": COMPETENCY_LABELS,
        "server_keys": {p: server_fallback_available(p) for p in ("groq", "openai", "elevenlabs")},
    }


@router.post("/auth/google")
def google_sign_in(request: dict) -> dict:
    try:
        claims = verify_id_token(str(request.get("credential", "")))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    user = google_user(claims["sub"], claims["email"], claims.get("name", ""), claims.get("picture", ""))
    return {"token": issue_token(user["id"]), "user": user}


# ---------------------------------------------------------------- account


@router.get("/studio/account")
def get_account(user: dict = Depends(current_user)) -> dict:
    return {"account": account_info(user["id"]), "usage": usage_summary(user["id"])}


@router.patch("/studio/account")
def patch_account(request: dict, user: dict = Depends(current_user)) -> dict:
    if "name" in request:
        update_name(user["id"], str(request["name"]))
    if request.get("new_password"):
        try:
            set_password(user["id"], str(request["new_password"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"account": account_info(user["id"])}


@router.post("/studio/account/sign-out-others")
def sign_out_others(user: dict = Depends(current_user), authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    return {"revoked": revoke_tokens(user["id"], hashlib.sha256(token.encode()).hexdigest())}


@router.post("/studio/account/sign-out")
def sign_out(user: dict = Depends(current_user), authorization: str | None = Header(default=None)) -> dict:
    token = (authorization or "").removeprefix("Bearer ").strip()
    with connection() as db:
        db.execute("DELETE FROM auth_tokens WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))
    return {"ok": True}


@router.get("/studio/account/export")
def export_account(user: dict = Depends(current_user)) -> dict:
    return export_user_data(user["id"])


@router.delete("/studio/account")
def remove_account(request: dict, user: dict = Depends(current_user)) -> dict:
    if str(request.get("confirm", "")).strip().lower() != user["email"].lower():
        raise HTTPException(status_code=400, detail="Type your email to confirm")
    delete_account(user["id"])
    return {"ok": True}


# ---------------------------------------------------------------- profile


@router.get("/studio/profile")
def profile(user: dict = Depends(current_user)) -> dict:
    return {**get_profile(user["id"]), "user": user}


@router.put("/studio/profile")
def update_profile(request: dict, user: dict = Depends(current_user)) -> dict:
    return save_profile(
        user["id"],
        prefs=request.get("prefs") if isinstance(request.get("prefs"), dict) else None,
        target=request.get("target") if isinstance(request.get("target"), dict) else None,
        onboarding_done=request.get("onboarding_done") if isinstance(request.get("onboarding_done"), bool) else None,
    )


# ---------------------------------------------------------------- intake


@router.post("/studio/intake/parse")
def intake_parse(request: dict, user: dict = Depends(current_user)) -> dict:
    text = str(request.get("text", "")).strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Tell us a little about the interview you want to practise")
    provider_runtime(user["id"], "llm")
    return parse_goal(user["id"], text, str(request.get("job_description", "")))


@router.post("/studio/intake/answer")
def intake_answer(request: dict, user: dict = Depends(current_user)) -> dict:
    return apply_answers(request.get("target") or {}, request.get("answers") or {})


@router.post("/studio/intake/brief")
def intake_brief(request: dict, user: dict = Depends(current_user)) -> dict:
    target = request.get("target") or {}
    provider_runtime(user["id"], "llm")
    brief = role_brief(user["id"], target, refresh=bool(request.get("refresh")))
    save_profile(user["id"], target=target)
    return {"brief": brief}


@router.get("/studio/resume/digest")
def resume_digest_route(refresh: bool = False, user: dict = Depends(current_user)) -> dict:
    return {"digest": digest_resume(user["id"], refresh=refresh)}


# ---------------------------------------------------------------- interviews


@router.post("/studio/interviews")
def start(request: dict, user: dict = Depends(current_user)) -> dict:
    provider_runtime(user["id"], "llm")
    target = request.get("target") or {}
    brief = request.get("brief") or {}
    minutes = int(request.get("minutes") or 30)
    if minutes not in ALLOWED_MINUTES:
        raise HTTPException(status_code=400, detail="Choose 15, 30, 45 or 60 minutes")
    prefs = get_profile(user["id"])["prefs"]
    persona = str(request.get("persona") or prefs.get("persona") or "maya")
    if persona not in PERSONAS:
        persona = "maya"
    expire_candidates(user["id"])
    plan = build_plan(user["id"], target, brief, minutes)
    utterance = opening(persona, target, plan, minutes, user.get("name", ""))
    state = new_state(plan, minutes, utterance)
    state["prefs"] = {"pressure": prefs.get("pressure", "realistic"), "memory_enabled": prefs.get("memory_enabled", True)}
    session_id = str(uuid.uuid4())
    role = ROLE_FAMILIES.get(target.get("role_family", ""), {}).get("label", "Interview")
    title = " · ".join(x for x in [target.get("company"), target.get("role_title") or role, LEVELS.get(target.get("level", ""), {}).get("label")] if x)
    create_studio_interview(session_id, user["id"], target, plan, state, persona, title or "Practice interview", minutes)
    save_profile(user["id"], prefs={"persona": persona})
    return {
        "session_id": session_id,
        "title": title,
        "persona": persona,
        "utterance": utterance,
        "plan": [{"kind": p["kind"], "label": ROUNDS.get(p["kind"], {}).get("label", p["kind"])} for p in plan],
        "phase": state["phase"],
        "index": 0,
        "total": len(plan),
        "remaining_seconds": minutes * 60,
        "current_kind": plan[0]["kind"],
    }


@router.get("/studio/interviews")
def interviews(user: dict = Depends(current_user)) -> dict:
    return {"interviews": list_studio_interviews(user["id"])}


@router.get("/studio/interviews/{session_id}")
def interview_detail(session_id: str, user: dict = Depends(current_user)) -> dict:
    interview = _interview(session_id, user["id"])
    state = interview["state"]
    return {
        "session_id": session_id,
        "title": interview["title"],
        "persona": interview["persona"],
        "status": interview["status"],
        "target": interview["target"],
        "created_at": interview["created_at"],
        "phase": state.get("phase"),
        "transcript": state.get("transcript", []),
        "plan": [{"kind": p["kind"], "label": ROUNDS.get(p["kind"], {}).get("label", p["kind"]), "status": p.get("status")} for p in interview["plan"]],
        "index": state.get("index", 0),
        "total": len(interview["plan"]),
        "report": interview["report"],
    }


def _run_turn(user: dict, session_id: str, text: str, code: str) -> dict:
    interview = _interview(session_id, user["id"])
    if interview["state"].get("phase") == "done" or interview["status"] == "completed":
        raise HTTPException(status_code=409, detail="This interview has ended")
    prefs = {**get_profile(user["id"])["prefs"], **interview["state"].get("prefs", {})}
    try:
        return take_turn(user["id"], interview, text, code, prefs)
    except ModelError as exc:
        raise _model_error(exc) from exc


@router.post("/studio/interviews/{session_id}/turn")
def turn(session_id: str, request: dict, user: dict = Depends(current_user)) -> dict:
    return _run_turn(user, session_id, str(request.get("text", ""))[:8000], str(request.get("code", ""))[:12000])


@router.post("/studio/transcribe")
async def transcribe(audio: UploadFile = File(...), user: dict = Depends(current_user)) -> dict:
    provider, key = provider_runtime(user["id"], "transcription")
    payload = await audio.read()
    if not payload:
        return {"text": ""}
    if len(payload) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Recording is too long. Try answering in shorter parts.")
    suffix = Path(audio.filename or "answer.webm").suffix or ".webm"
    if suffix not in {".webm", ".ogg", ".mp4", ".m4a", ".wav", ".mp3"}:
        suffix = ".webm"
    handle, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(payload)
        text = transcribe_file(provider, key, path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Couldn't transcribe that recording. Try again or type your answer.") from exc
    finally:
        Path(path).unlink(missing_ok=True)  # recordings are never kept
    return {"text": text}


@router.post("/studio/interviews/{session_id}/hint")
def hint(session_id: str, user: dict = Depends(current_user)) -> dict:
    interview = _interview(session_id, user["id"])
    state = interview["state"]
    state["hints"] = state.get("hints", 0) + 1
    save_studio_state(session_id, state)
    return {"hint": coach_hint(user["id"], interview), "hints_used": state["hints"]}


@router.post("/studio/interviews/{session_id}/finish")
def finish(session_id: str, user: dict = Depends(current_user)) -> dict:
    interview = _interview(session_id, user["id"])
    if interview["report"]:
        return {"report": interview["report"]}
    state = interview["state"]
    state["phase"] = "done"
    save_studio_state(session_id, state)
    interview["memory_enabled"] = state.get("prefs", {}).get("memory_enabled", True)
    report = final_report(user["id"], interview)
    return {"report": report}


@router.post("/studio/interviews/{session_id}/retry")
def retry(session_id: str, request: dict, user: dict = Depends(current_user)) -> dict:
    interview = _interview(session_id, user["id"])
    report = interview["report"] or {}
    number = int(request.get("number", 0))
    question = next((q for q in report.get("questions", []) if q["number"] == number), None)
    answer = str(request.get("answer", "")).strip()
    if not question or len(answer) < 10:
        raise HTTPException(status_code=400, detail="Write or record a fuller answer to compare")
    try:
        return retry_answer(user["id"], question, answer)
    except ModelError as exc:
        raise _model_error(exc) from exc


@router.delete("/studio/interviews/{session_id}")
def remove_interview(session_id: str, user: dict = Depends(current_user)) -> dict:
    return {"ok": delete_studio_interview(user["id"], session_id)}


# ---------------------------------------------------------------- voice


@router.get("/studio/voices")
def voices(user: dict = Depends(current_user)) -> dict:
    return {"voices": available_voices(user["id"])}


@router.post("/studio/speak")
def speak_route(request: dict, user: dict = Depends(current_user)) -> Response:
    text = str(request.get("text", "")).strip()[:2400]
    persona = str(request.get("persona") or "maya")
    voice_pref = str(request.get("voice") or get_profile(user["id"])["prefs"].get("voice", "auto"))
    provider, _ = resolve_voice(persona, voice_pref)
    if provider == "browser" or not (optional_voice_key(user["id"], "groq") or optional_voice_key(user["id"], "elevenlabs")):
        raise HTTPException(status_code=424, detail="browser-voice")
    try:
        audio, media_type, used = speak(user["id"], text, persona, voice_pref)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="browser-voice") from exc
    return Response(content=audio, media_type=media_type, headers={"Cache-Control": "private, max-age=86400", "X-Voice": used})


# ---------------------------------------------------------------- memory


@router.get("/studio/memory")
def memory(user: dict = Depends(current_user)) -> dict:
    return {"items": list_memory(user["id"]), "focus": focus_competencies(user["id"])}


@router.post("/studio/memory")
def memory_add(request: dict, user: dict = Depends(current_user)) -> dict:
    kind = str(request.get("kind", "fact"))
    memory_id = add_memory(user["id"], kind, str(request.get("content", "")), str(request.get("topic", "")))
    if not memory_id:
        raise HTTPException(status_code=400, detail="That note can't be saved. Keep it about your interview practice, without sensitive personal details.")
    return {"id": memory_id}


@router.patch("/studio/memory/{memory_id}")
def memory_edit(memory_id: int, request: dict, user: dict = Depends(current_user)) -> dict:
    return {"ok": edit_memory(user["id"], memory_id, request)}


@router.delete("/studio/memory/{memory_id}")
def memory_delete(memory_id: int, user: dict = Depends(current_user)) -> dict:
    return {"ok": delete_memory(user["id"], memory_id)}


@router.delete("/studio/memory")
def memory_clear(user: dict = Depends(current_user)) -> dict:
    return {"deleted": clear_memory(user["id"])}


# ---------------------------------------------------------------- insights


@router.get("/studio/questions/stats")
def bank_stats(user: dict = Depends(current_user)) -> dict:
    return question_bank_stats()


@router.get("/studio/progress")
def progress(user: dict = Depends(current_user)) -> dict:
    items = [i for i in list_studio_interviews(user["id"], 100) if i["status"] == "completed"]
    trend = [{"date": i["completed_at"] or i["created_at"], "score": i["overall_score"], "title": i["title"]} for i in reversed(items)]
    return {"trend": trend[-20:], "focus": focus_competencies(user["id"]), "completed": len(items), "usage": usage_summary(user["id"])}
