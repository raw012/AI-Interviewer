"""Interview engine: plan, run turns, and write the coaching report.

Token strategy
- One model call per candidate turn. It scores the answer, updates a short
  rolling summary, proposes memory, and writes the interviewer's next line.
- The system prompt is fixed for a session (persona, pressure, target, rules)
  so providers can cache the prefix. Per-turn input is small: rolling notes
  (<= 600 chars), the last two exchanges clipped, the current question's rubric,
  and the next planned question.
- Openings and transitions that need no judgement are templated, not generated.

Evaluation approach (LLM-as-judge practice): an explicit rubric per question,
anchored 1-5 scale calibrated to the target level, evidence quoted from the
answer, per-competency scores, temperature 0, and an instruction not to reward
length. The overall score is computed from per-question scores, not asked for.
"""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone

from intake import default_loop, digest_resume
from knowledge import COMPETENCY_LABELS, LEVELS, PERSONAS, PRESSURE_STYLES, ROLE_FAMILIES, ROUNDS, company_info
from llm import ModelError, ask_json, clip
from memory import focus_competencies, memory_brief, record_review, remember, used_story_titles
from studio_store import (
    list_questions,
    save_exchange,
    save_studio_report,
    save_studio_state,
    studio_exchanges,
    trending_for,
    user_question_history,
)

MINUTES_PER_KIND = {
    "coding": 18, "system_design": 22, "ml_system_design": 20, "object_design": 15,
    "frontend": 12, "product_sense": 12, "product_execution": 10, "analytics_case": 10,
    "behavioral": 6, "recruiter_screen": 4, "resume_deep_dive": 7,
}
MAX_FOLLOWUPS = {"coding": 3, "system_design": 4, "ml_system_design": 4, "object_design": 3, "behavioral": 2, "recruiter_screen": 1}
ANCHORS = (
    "Score anchors relative to the target level: 1 = no relevant content or wrong; 2 = partial, major gaps; "
    "3 = acceptable but borderline at this level; 4 = clear pass at this level; 5 = exceptional, would stand out. "
    "Do not reward length or confident tone; reward specific, correct, well-reasoned content. Quote short evidence."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- planning


def _resume_items(user_id: str, count: int) -> list[dict]:
    digest = digest_resume(user_id) or {}
    items = []
    for project in (digest.get("projects") or [])[:count]:
        probes = [p for p in project.get("probe", []) if isinstance(p, str)]
        if not project.get("name"):
            continue
        text = f"I'd like to hear about {project['name']} from your resume. Walk me through what it does and the part you personally built."
        items.append({
            "id": f"resume:{re.sub('[^a-z0-9]+', '-', project['name'].lower())[:40]}",
            "kind": "resume_deep_dive",
            "text": text,
            "competencies": ["technical_depth", "ownership", "communication"],
            "rubric": ["Clear overview of the problem and system", "Personal contribution separated from the team's", "A real decision with alternatives", "Evidence for claims: " + "; ".join(project.get("claims", [])[:2])],
            "followups": probes[:3] or ["What was the hardest technical decision?", "What would you change now?"],
            "pitfalls": ["Vague 'we did' answers", "Claims without numbers or evidence"],
            "provenance": "from_your_resume",
            "source_note": "Generated from your uploaded resume.",
            "difficulty": 3,
        })
    return items


def _score_question(q: dict, role: str, level: str, ckey: str, focus: list[str], history: dict, trend: dict | None = None) -> float:
    score = float(q.get("priority", 0.5))
    extras = q.get("extras") or {}
    if extras.get("harness"):
        score += 0.3  # runnable problems give a better coding round
    if trend and extras.get("ref") in trend:
        score += 0.25 + 0.5 * trend[extras["ref"]]  # reported recently for this company
    if q["role_families"] and role not in q["role_families"]:
        return -1
    if q["levels"] and level not in q["levels"]:
        score -= 0.5
    if q["companies"]:
        score += 0.35 if ckey in q["companies"] else -0.25
    if focus and set(q["competencies"]) & set(focus):
        score += 0.3
    past = history.get(q["id"])
    if past:
        days = (_now() - datetime.fromisoformat(past["last_asked"])).days if past.get("last_asked") else 99
        if days < 14:
            score -= 0.7
        if (past.get("avg_score") or 0) >= 4:
            score -= 0.4
        elif (past.get("avg_score") or 5) <= 2.5 and days >= 3:
            score += 0.2  # spaced retry of a question that went badly
    return score + random.uniform(0, 0.15)


def build_plan(user_id: str, target: dict, brief: dict, minutes: int) -> list[dict]:
    role = target.get("role_family") or "software_engineering"
    level = target.get("level") or ("intern" if target.get("employment") == "internship" else "new_grad")
    ckey = target.get("company_key", "")
    rounds = [x["round"] for x in brief.get("loop", [])] or target.get("rounds") or default_loop(role, level)
    if target.get("rounds"):
        rounds = target["rounds"]
    focus = focus_competencies(user_id)
    history = user_question_history(user_id)
    bank = list_questions(set(rounds) | {"recruiter_screen", "behavioral"})
    company_trend = trending_for(ckey) if ckey else {}
    trend = company_trend or trending_for("")
    # Fit the loop into the session length, keeping round order and variety.
    plan: list[dict] = []
    used: set[str] = set()
    budget = minutes - 3  # opening and wrap-up

    def pick(kind: str) -> dict | None:
        pool = [q for q in bank if q["kind"] == kind and q["id"] not in used]
        scored = [(_score_question(q, role, level, ckey, focus, history, trend), q) for q in pool]
        scored = sorted([x for x in scored if x[0] > 0], key=lambda x: x[0], reverse=True)
        if not scored:
            return None
        best = dict(scored[0][1])
        ref = (best.get("extras") or {}).get("ref")
        if ref and ref in company_trend:
            best["trending"] = f"Reported by candidates at {target.get('company') or ckey.title()} in the last 30 days"
        elif ref and ref in trend:
            best["trending"] = "Reported by candidates at major tech companies in the last 30 days"
        return best

    # Opener for non-technical-only sessions
    if not set(rounds) <= {"coding", "system_design", "sql", "statistics"}:
        opener = next((q for q in bank if q["id"] == "open-intro"), None)
        if opener:
            plan.append(opener)
            used.add(opener["id"])
            budget -= MINUTES_PER_KIND["recruiter_screen"]
    resume_queue = _resume_items(user_id, 2) if "resume_deep_dive" in rounds or role in ("software_engineering", "ml_engineering") else []
    cycle = 0
    while budget > 3 and cycle < 12:
        progressed = False
        for kind in rounds:
            cost = MINUTES_PER_KIND.get(kind, 8)
            if budget - cost < -2:
                continue
            if kind == "resume_deep_dive" and resume_queue:
                item = resume_queue.pop(0)
            else:
                item = pick(kind)
            if not item:
                continue
            plan.append(item)
            used.add(item["id"])
            budget -= cost
            progressed = True
            if budget <= 3:
                break
        cycle += 1
        if not progressed:
            break
    if not plan:
        fallback = pick("behavioral") or {"id": "open-intro", "kind": "recruiter_screen", "text": "Tell me about yourself.", "competencies": ["communication"], "rubric": [], "followups": [], "pitfalls": []}
        plan.append(fallback)
    return [_plan_item(q) for q in plan]


def _plan_item(q: dict) -> dict:
    return {
        "id": q["id"],
        "kind": q["kind"],
        "text": q["text"],
        "competencies": q.get("competencies", []),
        "rubric": q.get("rubric", []),
        "followups": q.get("followups", []),
        "pitfalls": q.get("pitfalls", []),
        "provenance": q.get("provenance", "practice"),
        "source_note": q.get("source_note", ""),
        "source_urls": q.get("source_urls", []),
        "difficulty": q.get("difficulty", 2),
        "extras": q.get("extras") or {},
        "trending": q.get("trending", ""),
        "status": "pending",
    }


def _adapt(plan: list[dict], index: int, recent: list[float], target: dict) -> None:
    """Swap the next pending question for a harder or easier one of the same kind."""
    nxt = index + 1
    if nxt >= len(plan) or len(recent) < 2 or plan[nxt]["provenance"] == "from_your_resume":
        return
    avg = sum(recent[-2:]) / 2
    current = plan[nxt]
    want = current["difficulty"] + (1 if avg >= 4.3 else -1 if avg <= 2.0 else 0)
    if want == current["difficulty"]:
        return
    role = target.get("role_family") or "software_engineering"
    used = {p["id"] for p in plan}
    options = [q for q in list_questions([current["kind"]])
               if q["id"] not in used and q["difficulty"] == want and (not q["role_families"] or role in q["role_families"])]
    if options:
        options.sort(key=lambda q: q["priority"], reverse=True)
        plan[nxt] = {**_plan_item(options[0]), "adapted": "harder" if want > current["difficulty"] else "easier"}


# ---------------------------------------------------------------- prompts


def persona_for(key: str) -> dict:
    return PERSONAS.get(key) or PERSONAS["maya"]


def system_prompt(target: dict, persona_key: str, pressure: str) -> str:
    persona = persona_for(persona_key)
    level = target.get("level") or "new_grad"
    info = company_info(target.get("company", "")) or {}
    company = target.get("company") or "a top tech company"
    role = target.get("role_title") or ROLE_FAMILIES.get(target.get("role_family", ""), {}).get("label", "Software Engineering")
    values = "; ".join(info.get("values", [])[:4])
    return f"""You are {persona['name']}, {persona['title']} at {company}, running a realistic mock interview for a {LEVELS.get(level, {}).get('label', level)} {role} {'internship' if target.get('employment') == 'internship' else 'position'}.
Personality: {persona['style']}
Pressure: {PRESSURE_STYLES.get(pressure, PRESSURE_STYLES['realistic'])}
Level bar: {LEVELS.get(level, {}).get('expectation', '')}
{f'Company values to probe naturally: {values}' if values else ''}

How you speak: like a real person on a video call. Short sentences, contractions, one question at a time, no lists or markdown, no emojis. Acknowledge briefly and specifically (never "Great answer!"; never reveal scores or coach during the interview). Do not repeat the candidate's answer back. Keep each turn under 70 words unless presenting a new problem.

Each turn you receive the current question, its rubric, and the candidate's latest reply. Decide:
- "follow_up": probe the most important gap or claim (why, how, numbers, trade-offs, what you personally did, edge cases, complexity). Never ask what they already answered.
- "next": the topic is covered well enough or follow-ups are used up; transition in one short clause and ask the NEXT planned question exactly in substance.
- "clarify": the candidate asked you a question (repeat, clarify scope, ask for a hint). Answer it as an interviewer would; give a hint only if pressure allows. No assessment needed.
- "wrap": only when told time is up.

{ANCHORS}

Return only JSON:
{{"action": "follow_up|next|clarify|wrap",
 "assessment": {{"score": 1-5, "dimensions": {{"<competency>": 1-5}}, "strengths": ["short"], "missing": ["short, specific"], "evidence": "short quote from the answer"}} or null for clarify,
 "utterance": "what you say out loud next",
 "notes": "updated running summary of the whole interview so far, max 500 characters, facts and signals only",
 "memory": [{{"kind": "growth|strength|story|fact|preference", "topic": "<competency or ''>", "title": "short", "content": "one sentence", "evidence": "short", "confidence": 0-1}}]}}
Memory: propose 0-2 items, only durable, useful observations about interview skills, STAR stories used, or stated career facts. Never health, family, age, ethnicity, religion, politics, immigration, salary or personality judgements."""


def _turn_prompt(state: dict, item: dict, next_item: dict | None, answer: str, code: str, remaining: int, depth: int, max_depth: int, memory_lines: str, run: dict | None = None) -> str:
    tail = "\n".join(f"Q: {clip(t['q'], 220)}\nA: {clip(t['a'], 380)}" for t in state.get("tail", [])[-2:])
    parts = [
        f"Time left: ~{max(0, remaining // 60)} min. Follow-ups used on this question: {depth}/{max_depth}.",
        f"Running notes: {state.get('notes') or '(start of interview)'}",
    ]
    if memory_lines and state.get("number", 0) < 3:
        parts.append(f"From previous sessions (use to probe, never mention you remember):\n{memory_lines}")
    parts += [
        f"Current question ({ROUNDS.get(item['kind'], {}).get('label', item['kind'])}): {item['text']}",
        f"Competencies: {', '.join(item['competencies'])}",
        f"Rubric: {' | '.join(item['rubric'])}",
        f"Useful follow-ups: {' | '.join(item['followups'][:3])}",
        f"Common pitfalls: {' | '.join(item['pitfalls'][:2])}",
    ]
    if tail:
        parts.append(f"Recent exchanges:\n{tail}")
    parts.append(f"You just asked: {clip(state.get('last_prompt', ''), 400)}")
    parts.append(f"Candidate replied: {clip(answer, 3500) or '(silence / no answer)'}")
    if code.strip():
        parts.append(f"Candidate's code ({(run or {}).get('language', 'unspecified language')}):\n{clip(code, 3000)}")
    if run and run.get("total"):
        failing = "; ".join(str(x)[:120] for x in (run.get("failing") or [])[:3])
        parts.append(
            f"They ran the test suite in the workspace: {run.get('passed', 0)}/{run['total']} tests passed."
            + (f" Failing: {failing}" if failing else "")
            + " Score correctness on these real results, not on how the code looks."
        )
    elif (item.get("extras") or {}).get("harness") and code.strip():
        parts.append("They have not run the tests yet. A real interviewer would ask them to test before moving on.")
    if next_item:
        parts.append(f"NEXT planned question (use if action is next): {next_item['text']}")
    else:
        parts.append("This is the last planned question. If you move on, choose action wrap.")
    if depth >= max_depth:
        parts.append("Follow-up limit reached: choose next (or wrap if none).")
    if remaining < 120:
        parts.append("Time is up: choose wrap.")
    return "\n".join(parts)


# ---------------------------------------------------------------- session lifecycle


def opening(persona_key: str, target: dict, plan: list[dict], minutes: int, user_name: str = "") -> str:
    persona = persona_for(persona_key)
    first = persona["name"].split()[0]
    name = f" {user_name.split()[0]}" if user_name else ""
    kinds = []
    for p in plan:
        label = ROUNDS.get(p["kind"], {}).get("label", "").lower()
        if label and label not in kinds and p["kind"] != "recruiter_screen":
            kinds.append(label)
    agenda = " and ".join(kinds[:2]) if kinds else "a few questions"
    company = f" here at {target['company']}" if target.get("company") else ""
    return (
        f"Hi{name}, I'm {first}, {persona['title'].lower()}{company}. Thanks for making the time. "
        f"We've got about {minutes} minutes, mostly {agenda}. Think out loud, and feel free to ask clarifying questions. "
        f"{plan[0]['text']}"
    )


def new_state(plan: list[dict], minutes: int, first_utterance: str) -> dict:
    plan[0]["status"] = "asked"
    return {
        "phase": "question",
        "index": 0,
        "depth": 0,
        "number": 0,
        "notes": "",
        "scores": [],
        "tail": [],
        "last_prompt": first_utterance,
        "started_at": _now().isoformat(),
        "deadline": (_now() + timedelta(minutes=minutes)).isoformat(),
        "transcript": [{"role": "interviewer", "text": first_utterance}],
    }


def remaining_seconds(state: dict) -> int:
    try:
        return max(0, int((datetime.fromisoformat(state["deadline"]) - _now()).total_seconds()))
    except Exception:
        return 0


def take_turn(user_id: str, interview: dict, answer: str, code: str = "", prefs: dict | None = None, run: dict | None = None) -> dict:
    prefs = prefs or {}
    state, plan, target = interview["state"], interview["plan"], interview["target"]
    session_id = interview["session_id"]
    answer = (answer or "").strip()
    state.setdefault("transcript", []).append({"role": "candidate", "text": answer, **({"code": code} if code.strip() else {})})

    if state["phase"] == "wrap":
        return _closing(user_id, interview, answer)

    index = state["index"]
    item = plan[index]
    next_item = plan[index + 1] if index + 1 < len(plan) else None
    depth = state.get("depth", 0)
    max_depth = MAX_FOLLOWUPS.get(item["kind"], 2)
    if prefs.get("pressure") == "tough":
        max_depth += 1
    remaining = remaining_seconds(state)
    memory_lines = memory_brief(user_id, item["competencies"]) if prefs.get("memory_enabled", True) else ""
    if memory_lines and state.get("number", 0) < 3:
        stories = used_story_titles(user_id)
        if stories:
            memory_lines += "\nStories already used before: " + "; ".join(stories[:5])

    system = system_prompt(target, interview.get("persona") or prefs.get("persona", "maya"), prefs.get("pressure", "realistic"))
    prompt = _turn_prompt(state, item, next_item, answer, code, remaining, depth, max_depth, memory_lines, run)
    try:
        result = ask_json(user_id, "turn", prompt, system=system, session_id=session_id, effort="low", max_tokens=900, temperature=0.3)
    except ModelError:
        result = {"action": "next" if next_item else "wrap", "assessment": None,
                  "utterance": "", "notes": state.get("notes", ""), "memory": []}

    action = result.get("action") if result.get("action") in ("follow_up", "next", "clarify", "wrap") else "next"
    if action == "follow_up" and depth >= max_depth:
        action = "next"
    if remaining < 120 and action != "clarify":
        action = "wrap"
    if action == "next" and not next_item:
        action = "wrap"

    assessment = result.get("assessment") if isinstance(result.get("assessment"), dict) else None
    response: dict = {"action": action}
    if action != "clarify":
        assessment = _clean_assessment(assessment, item)
        if run and run.get("total"):
            assessment["tests"] = {"passed": int(run.get("passed", 0)), "total": int(run["total"]), "language": str(run.get("language", ""))[:20]}
        state["number"] += 1
        exchange = {
            "number": state["number"],
            "question": state.get("last_prompt", item["text"]),
            "answer": answer,
            "topic": item["kind"],
            "assessment": assessment,
            "code": code,
            "question_id": item["id"],
            "kind": "main" if depth == 0 else "followup",
        }
        answer_id = save_exchange(user_id, session_id, exchange)
        state["scores"].append({"id": item["id"], "score": assessment["score"], "depth": depth, "competencies": assessment["dimensions"]})
        if prefs.get("memory_enabled", True):
            remember(user_id, result.get("memory") or [], session_id, answer_id)
        state["tail"] = (state.get("tail", []) + [{"q": exchange["question"], "a": answer}])[-2:]
        response["assessment"] = {"score": assessment["score"]}  # details stay hidden until the report
    state["notes"] = clip(str(result.get("notes") or state.get("notes", "")), 600)

    utterance = str(result.get("utterance") or "").strip()
    if action == "follow_up":
        state["depth"] = depth + 1
    elif action == "next":
        item["status"] = "done"
        main_scores = [s["score"] for s in state["scores"] if s["depth"] == 0]
        _adapt(plan, index, main_scores, target)
        state["index"] = index + 1
        state["depth"] = 0
        upcoming = plan[state["index"]]
        upcoming["status"] = "asked"
        if not utterance or _too_different(utterance, upcoming["text"]):
            utterance = f"{_transition()} {upcoming['text']}"
    elif action == "wrap":
        item["status"] = "done"
        state["phase"] = "wrap"
        utterance = _wrap_line(utterance)
    if not utterance:
        utterance = "Could you say a bit more about that?"
    state["last_prompt"] = utterance
    state["transcript"].append({"role": "interviewer", "text": utterance})
    save_studio_state(session_id, state, plan)
    response.update(_progress(state, plan))
    response["utterance"] = utterance
    return response


def _too_different(utterance: str, question: str) -> bool:
    q = set(re.findall(r"[a-z]{4,}", question.lower()))
    u = set(re.findall(r"[a-z]{4,}", utterance.lower()))
    return bool(q) and len(q & u) / len(q) < 0.35


def _transition() -> str:
    return random.choice(["Okay, thanks. Let's switch gears.", "Got it. Let's move on.", "Thanks, that's helpful. Next one.", "Alright. Let's try something different."])


def _wrap_line(utterance: str) -> str:
    base = utterance if utterance and "question" in utterance.lower() else ""
    return base or "That's about all the time we have for my questions. Before we wrap up, is there anything you'd like to ask me?"


def _closing(user_id: str, interview: dict, answer: str) -> dict:
    state = interview["state"]
    lowered = answer.lower()
    if not answer or re.search(r"\b(no|nope|nothing|that's all|i'm good|im good)\b", lowered) and len(answer) < 60:
        utterance = "Great. Thanks again for your time today. I'll put together your feedback now."
    else:
        persona = persona_for(interview.get("persona", "maya"))
        try:
            result = ask_json(
                user_id, "closing",
                f"Candidate asked at the end of the interview: {clip(answer, 800)}\nAnswer in 2-3 natural spoken sentences as {persona['name']}, {persona['title']}, without inventing confidential specifics, then thank them and close. Return JSON {{\"utterance\": \"...\"}}",
                session_id=interview["session_id"], effort="low", max_tokens=300, temperature=0.5,
            )
            utterance = str(result.get("utterance") or "")
        except ModelError:
            utterance = ""
        utterance = utterance or "Good question. Thanks again for your time today. I'll put together your feedback now."
    state["phase"] = "done"
    state["transcript"].append({"role": "interviewer", "text": utterance})
    save_studio_state(interview["session_id"], state, interview["plan"])
    return {"action": "end", "utterance": utterance, **_progress(state, interview["plan"])}


def _clean_assessment(raw: dict | None, item: dict) -> dict:
    raw = raw or {}
    try:
        score = float(raw.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    score = min(5.0, max(1.0, score)) if score else 2.5
    dims = {}
    for key, value in (raw.get("dimensions") or {}).items():
        if key in COMPETENCY_LABELS:
            try:
                dims[key] = min(5.0, max(1.0, float(value)))
            except (TypeError, ValueError):
                continue
    if not dims:
        dims = {c: score for c in item["competencies"][:3]}
    return {
        "score": round(score, 1),
        "dimensions": dims,
        "strengths": [str(x)[:160] for x in (raw.get("strengths") or [])][:3],
        "missing": [str(x)[:160] for x in (raw.get("missing") or [])][:3],
        "evidence": str(raw.get("evidence") or "")[:240],
    }


def _progress(state: dict, plan: list[dict]) -> dict:
    return {
        "phase": state["phase"],
        "index": state["index"],
        "total": len(plan),
        "depth": state.get("depth", 0),
        "remaining_seconds": remaining_seconds(state),
        "current_kind": plan[min(state["index"], len(plan) - 1)]["kind"],
        "problem": problem_view(plan[min(state["index"], len(plan) - 1)]),
    }


def problem_view(item: dict) -> dict | None:
    """What the code workspace needs for the current question."""
    extras = item.get("extras") or {}
    if item["kind"] not in ("coding", "sql", "frontend", "object_design") and not extras.get("harness"):
        return None
    return {
        "id": item["id"],
        "title": extras.get("title") or ROUNDS.get(item["kind"], {}).get("label", "Problem"),
        "text": item["text"],
        "harness": extras.get("harness"),
        "provenance": item.get("provenance", "practice"),
        "trending": item.get("trending", ""),
    }


# ---------------------------------------------------------------- coaching


HINT_SYSTEM = """You are a Socratic interview coach. The candidate is stuck mid-interview. Do NOT give the answer.
Give one guiding question or a small nudge that helps them find the next step themselves, in under 35 words, spoken style.
Return JSON {"hint": "..."}"""


def coach_hint(user_id: str, interview: dict) -> str:
    state, plan = interview["state"], interview["plan"]
    item = plan[min(state["index"], len(plan) - 1)]
    last = state["transcript"][-1]["text"] if state.get("transcript") else ""
    prompt = (
        f"Question: {item['text']}\nRubric: {' | '.join(item['rubric'])}\nInterviewer's last line: {clip(state.get('last_prompt', ''), 300)}\n"
        f"Candidate so far: {clip(last if state['transcript'][-1]['role'] == 'candidate' else '', 800) or '(nothing yet)'}"
    )
    try:
        return str(ask_json(user_id, "hint", prompt, system=HINT_SYSTEM, session_id=interview["session_id"], effort="low", max_tokens=200).get("hint", ""))[:300]
    except ModelError:
        return "What's the very first thing you'd want to clarify or define before going further?"


REPORT_SYSTEM = """You are an expert interview coach writing feedback after a mock interview. Be honest, specific and kind.
Teach like a great mentor: point to evidence from the candidate's own words, explain why it matters at their target level, and guide with questions (Socratic) before showing a better approach.
Return only JSON:
{"overall": {"readiness": "ready|close|developing", "headline": "one sentence", "summary": "3-4 sentences"},
 "competencies": [{"key": "<competency>", "score": 1-5, "evidence": "short", "next_step": "one concrete action"}],
 "questions": [{"number": <main question number>, "what_worked": ["..."], "what_was_missing": ["..."],
   "coach_questions": ["2-3 Socratic questions that lead the candidate to a stronger answer"],
   "better_outline": ["3-6 steps or beats of a strong answer at this level"],
   "sample_opening": "the first 1-2 sentences of a strong answer, in the candidate's voice"}],
 "patterns": ["up to 3 recurring habits across answers, positive or negative"],
 "next_session": {"focus": ["<competency keys>"], "plan": "2 sentences on what to practise next and how", "drills": ["2-3 short drills"]},
 "spoken_debrief": "about 90 words the interviewer would say aloud as a warm debrief: one strength, the top two improvements, encouragement",
 "memory": [{"kind": "growth|strength|story|fact|preference", "topic": "<competency>", "title": "short", "content": "one sentence", "evidence": "short", "confidence": 0-1}]}
Memory: up to 5 items that will make the NEXT interview better (recurring gaps, solid strengths, stories used). No sensitive personal data."""


def final_report(user_id: str, interview: dict) -> dict:
    session_id = interview["session_id"]
    exchanges = studio_exchanges(user_id, session_id)
    plan, target = interview["plan"], interview["target"]
    by_question: dict[str, list[dict]] = {}
    for ex in exchanges:
        by_question.setdefault(ex["question_id"] or str(ex["question_number"]), []).append(ex)
    groups = []
    for qid, items in by_question.items():
        plan_item = next((p for p in plan if p["id"] == qid), None)
        groups.append({"id": qid, "item": plan_item, "exchanges": items, "number": items[0]["question_number"]})

    competency_scores: dict[str, list[float]] = {}
    question_scores = []
    for group in groups:
        scores = [ex["assessment"].get("score") or ex["score"] for ex in group["exchanges"]]
        main = scores[0] if scores else 0
        follow = scores[1:]
        q_score = round(main * 0.6 + (sum(follow) / len(follow)) * 0.4, 2) if follow else main
        group["score"] = q_score
        question_scores.append(q_score)
        for ex in group["exchanges"]:
            for key, value in (ex["assessment"].get("dimensions") or {}).items():
                competency_scores.setdefault(key, []).append(float(value))
    overall_score = round(sum(question_scores) / len(question_scores), 2) if question_scores else 0

    lines = []
    for group in groups:
        item = group["item"] or {}
        lines.append(f"## Question {group['number']} ({item.get('kind', '')}) score {group['score']}: {item.get('text', group['exchanges'][0]['question'])}")
        lines.append(f"Rubric: {' | '.join(item.get('rubric', []))}")
        for ex in group["exchanges"]:
            a = ex["assessment"]
            lines.append(f"Asked: {clip(ex['question'], 240)}\nAnswer: {clip(ex['answer'], 900)}")
            if ex.get("code_text"):
                lines.append(f"Code: {clip(ex['code_text'], 900)}")
            lines.append(f"Turn score {a.get('score')}; missing: {'; '.join(a.get('missing', []))}")
    level = LEVELS.get(target.get("level", ""), {})
    prompt = (
        f"Target: {target.get('company') or 'general'} {target.get('role_title') or target.get('role_family')} — {level.get('label', '')}\n"
        f"Level bar: {level.get('expectation', '')}\nUser's focus: {target.get('focus', '')}\n"
        f"Computed overall score: {overall_score}/5\nPrevious memory:\n{memory_brief(user_id)}\n\n" + "\n".join(lines)
    )
    report: dict = {}
    if groups:
        try:
            report = ask_json(user_id, "report", prompt, system=REPORT_SYSTEM, session_id=session_id, effort="medium", max_tokens=3500, temperature=0.2)
        except ModelError:
            report = {}

    readiness = "ready" if overall_score >= 4 else "close" if overall_score >= 3 else "developing"
    overall = report.get("overall") if isinstance(report.get("overall"), dict) else {}
    overall = {
        "score": overall_score,
        "readiness": overall.get("readiness") if overall.get("readiness") in ("ready", "close", "developing") else readiness,
        "headline": overall.get("headline") or ("Solid session." if overall_score >= 3.5 else "Good practice; a few clear areas to improve."),
        "summary": overall.get("summary") or "",
    }
    model_comp = {c.get("key"): c for c in report.get("competencies", []) if isinstance(c, dict)}
    competencies = []
    for key, values in sorted(competency_scores.items(), key=lambda kv: sum(kv[1]) / len(kv[1])):
        extra = model_comp.get(key, {})
        competencies.append({
            "key": key,
            "label": COMPETENCY_LABELS.get(key, key),
            "score": round(sum(values) / len(values), 2),
            "evidence": extra.get("evidence", ""),
            "next_step": extra.get("next_step", ""),
        })
    model_q = {int(q.get("number", -1)): q for q in report.get("questions", []) if isinstance(q, dict) and str(q.get("number", "")).lstrip("-").isdigit()}
    questions = []
    for group in groups:
        item = group["item"] or {}
        extra = model_q.get(group["number"], {})
        first = group["exchanges"][0]
        questions.append({
            "number": group["number"],
            "question_id": group["id"],
            "kind": item.get("kind", first.get("exchange_kind", "")),
            "question": item.get("text", first["question"]),
            "provenance": item.get("provenance", "practice"),
            "source_note": item.get("source_note", ""),
            "source_urls": item.get("source_urls", []),
            "score": group["score"],
            "exchanges": [{"question": ex["question"], "answer": ex["answer"], "score": ex["assessment"].get("score"), "code": ex.get("code_text", "")} for ex in group["exchanges"]],
            "what_worked": extra.get("what_worked") or first["assessment"].get("strengths", []),
            "what_was_missing": extra.get("what_was_missing") or first["assessment"].get("missing", []),
            "coach_questions": extra.get("coach_questions", []),
            "better_outline": extra.get("better_outline") or item.get("rubric", []),
            "sample_opening": extra.get("sample_opening", ""),
        })
    next_session = report.get("next_session") if isinstance(report.get("next_session"), dict) else {}
    if not next_session.get("focus"):
        next_session["focus"] = [c["key"] for c in competencies[:2]]
    final = {
        "overall": overall,
        "competencies": competencies,
        "questions": questions,
        "patterns": report.get("patterns", [])[:3],
        "next_session": next_session,
        "spoken_debrief": report.get("spoken_debrief") or f"Thanks for practising today. {overall['headline']}",
        "target": target,
        "generated_at": _now().isoformat(),
    }
    save_studio_report(session_id, final, overall_score)
    if interview.get("memory_enabled", True):
        remember(user_id, report.get("memory") or [], session_id)
        for comp in competencies:
            record_review(user_id, comp["key"], comp["score"])
    return final


RETRY_SYSTEM = """You are a supportive interview coach. The candidate is re-answering a question after feedback.
Compare the new answer with the original against the rubric. Return only JSON:
{"score": 1-5, "improved": ["what got better"], "still_missing": ["what is still missing"], "coach_question": "one Socratic question to push further", "verdict": "one encouraging, honest sentence"}"""


def retry_answer(user_id: str, question: dict, new_answer: str) -> dict:
    prompt = (
        f"Question: {question['question']}\nRubric: {' | '.join(question.get('better_outline', []))}\n"
        f"Original answer (score {question.get('score')}): {clip(question['exchanges'][0]['answer'], 1200)}\n"
        f"New answer: {clip(new_answer, 2500)}\n{ANCHORS}"
    )
    result = ask_json(user_id, "retry", prompt, system=RETRY_SYSTEM, effort="low", max_tokens=700, temperature=0)
    try:
        result["score"] = round(min(5.0, max(1.0, float(result.get("score", 0)))), 1)
    except (TypeError, ValueError):
        result["score"] = None
    return result
