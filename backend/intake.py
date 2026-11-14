"""Intake: turn "what I want to practise" into a confirmed interview target.

1. parse_goal   free text -> structured target + the questions still missing
2. role_brief   target -> a short, sourced description of the real interview loop
                (cached per company/role/level; optional live web search)
3. digest_resume  resume text -> compact project digest used for deep-dive questions

Every model step has a rule-based fallback so intake still works if the model
call fails.
"""

from __future__ import annotations

import os
import re

import httpx

from knowledge import (
    COMPANIES,
    DEFAULT_LOOPS,
    LEVELS,
    ROLE_FAMILIES,
    ROUND_ALIASES,
    ROUNDS,
    company_info,
    company_key,
    match_alias,
)
from llm import ModelError, ask_json, clip
from storage import resume_for_user
from studio_store import get_brief, resume_digest, save_brief, save_resume_digest

TARGET_FIELDS = ("role_family", "role_title", "level", "employment", "company", "rounds", "job_description", "interview_date", "focus")

PARSE_SYSTEM = """You turn a job seeker's description of the interview they want to practise into JSON.
Return only JSON with keys:
role_family: one of software_engineering, frontend_engineering, ml_engineering, data_science, data_analytics, product_management, or "" if unclear
role_title: short job title as the user would say it, or ""
level: one of intern, new_grad, mid, senior, staff, or "" if not stated or implied
employment: "internship" or "full_time" or "" if unclear
company: company name or "" (do not guess)
rounds: list drawn from recruiter_screen, behavioral, coding, system_design, object_design, cs_fundamentals, frontend, ml_fundamentals, ml_system_design, product_sense, product_execution, analytics_case, statistics, sql, resume_deep_dive, mixed. Empty list if the user wants the real loop or did not say.
focus: one sentence on anything specific they want to work on, or ""
interview_date: as stated, or ""
Only fill a field when the text states or clearly implies it."""


def _rule_parse(text: str) -> dict:
    lowered = text.lower()
    level = match_alias(text, LEVELS) or ""
    employment = "internship" if level == "intern" or "intern" in lowered else ("full_time" if re.search(r"full[- ]?time|new grad|senior|staff|mid-level|l[3-7]\b|e[3-7]\b", lowered) else "")
    rounds = []
    for key, aliases in ROUND_ALIASES.items():
        if any(alias in lowered for alias in aliases) and key not in rounds:
            rounds.append(key)
    return {
        "role_family": match_alias(text, ROLE_FAMILIES) or "",
        "role_title": "",
        "level": level,
        "employment": employment,
        "company": (company_info(text) or {}).get("label", ""),
        "rounds": rounds,
        "focus": "",
        "interview_date": "",
    }


def _clean(raw: dict) -> dict:
    target: dict = {}
    role = str(raw.get("role_family") or "")
    target["role_family"] = role if role in ROLE_FAMILIES else ""
    target["role_title"] = str(raw.get("role_title") or "")[:80]
    level = str(raw.get("level") or "")
    target["level"] = level if level in LEVELS else ""
    employment = str(raw.get("employment") or "")
    target["employment"] = employment if employment in ("internship", "full_time") else ""
    if target["level"] == "intern":
        target["employment"] = "internship"
    elif target["employment"] == "internship" and not target["level"]:
        target["level"] = "intern"
    elif target["level"] and not target["employment"]:
        target["employment"] = "full_time"
    target["company"] = str(raw.get("company") or "")[:60].strip()
    target["company_key"] = company_key(target["company"])
    if target["company_key"] and not target["company"]:
        target["company"] = COMPANIES[target["company_key"]]["label"]
    rounds = raw.get("rounds") or []
    target["rounds"] = [r for r in rounds if r in ROUNDS][:6] if isinstance(rounds, list) else []
    target["focus"] = str(raw.get("focus") or "")[:240]
    target["interview_date"] = str(raw.get("interview_date") or "")[:40]
    target["job_description"] = str(raw.get("job_description") or "")[:6000]
    return target


def missing_questions(target: dict) -> list[dict]:
    """Ask only for what changes the interview: role, internship vs full-time, level, company."""
    questions = []
    if not target.get("role_family"):
        questions.append({
            "field": "role_family",
            "question": "Which kind of role is this for?",
            "options": [{"value": k, "label": v["label"]} for k, v in ROLE_FAMILIES.items()],
        })
    if not target.get("employment"):
        questions.append({
            "field": "employment",
            "question": "Is it an internship or a full-time position?",
            "options": [{"value": "internship", "label": "Internship"}, {"value": "full_time", "label": "Full-time"}],
        })
    if target.get("employment") == "full_time" and target.get("level") in ("", "intern"):
        questions.append({
            "field": "level",
            "question": "What level are you interviewing for?",
            "options": [{"value": k, "label": v["label"]} for k, v in LEVELS.items() if k != "intern"],
        })
    if not target.get("company"):
        questions.append({
            "field": "company",
            "question": "Which company is it with? Pick one, type another, or practise a general loop.",
            "options": [{"value": v["label"], "label": v["label"]} for v in list(COMPANIES.values())[:8]] + [{"value": "General", "label": "No specific company"}],
            "free_text": True,
        })
    return questions


def parse_goal(user_id: str, text: str, job_description: str = "") -> dict:
    text = (text or "").strip()[:2000]
    source = "model"
    try:
        raw = ask_json(
            user_id,
            "intake_parse",
            f"User wrote:\n{text}\n\nJob description (may be empty):\n{clip(job_description, 2500)}",
            system=PARSE_SYSTEM,
            effort="low",
            max_tokens=600,
            temperature=0,
        )
        rules = _rule_parse(text)
        for key, value in rules.items():  # rules fill gaps the model left empty
            if not raw.get(key) and value:
                raw[key] = value
        if not job_description.strip():
            # Level and internship vs full-time change the whole interview, so the
            # model may not guess them: keep them only when the text says so.
            if not rules["level"] and not re.search(r"\b(\d+\+? ?(years?|yrs?|yoe)|principal|lead)\b", text, re.I):
                raw["level"] = ""
            if not rules["employment"] and raw.get("level") != "intern":
                raw["employment"] = ""
    except (ModelError, Exception):
        raw = _rule_parse(text)
        source = "rules"
    raw["job_description"] = job_description
    target = _clean(raw)
    target["goal_text"] = text
    return {"target": target, "missing": missing_questions(target), "parsed_by": source}


def apply_answers(target: dict, answers: dict) -> dict:
    merged = dict(target)
    for key, value in (answers or {}).items():
        if key in TARGET_FIELDS:
            merged[key] = value
    if merged.get("company") in ("General", "general", "none"):
        merged["company"] = ""
        merged["company_general"] = True
    cleaned = _clean(merged)
    cleaned["goal_text"] = target.get("goal_text", "")
    cleaned["company_general"] = merged.get("company_general", False)
    return {"target": cleaned, "missing": [q for q in missing_questions(cleaned) if not (q["field"] == "company" and cleaned.get("company_general"))]}


# ---------------------------------------------------------------- role brief


def default_loop(role_family: str, level: str) -> list[str]:
    loops = DEFAULT_LOOPS.get(role_family or "software_engineering") or DEFAULT_LOOPS["software_engineering"]
    return list(loops.get(level or "new_grad") or loops.get("new_grad") or ["behavioral"])


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Optional live search. Uses Tavily or Brave only if the server has a key."""
    tavily = os.getenv("TAVILY_API_KEY", "").strip()
    brave = os.getenv("BRAVE_API_KEY", "").strip()
    try:
        if tavily:
            response = httpx.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily, "query": query, "max_results": max_results, "search_depth": "basic"},
                timeout=12,
            )
            response.raise_for_status()
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": clip(r.get("content", ""), 400)}
                for r in response.json().get("results", [])
            ]
        if brave:
            response = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": brave, "Accept": "application/json"},
                timeout=12,
            )
            response.raise_for_status()
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": clip(re.sub("<[^>]+>", "", r.get("description", "")), 400)}
                for r in response.json().get("web", {}).get("results", [])
            ]
    except Exception:
        return []
    return []


BRIEF_SYSTEM = """You are a careful interview researcher. Describe what a candidate should expect in this interview loop.
Use the provided company notes and search snippets as your evidence. Do not invent specific facts (exact number of rounds, named questions) that the evidence does not support; say "commonly reported" or "typically" when evidence is partial.
Return only JSON:
{"summary": "2-3 sentences",
 "loop": [{"round": "<round key from the allowed list>", "focus": "what this round tests here, one sentence"}],
 "look_for": ["3-5 short bullets of what interviewers at this company/level look for"],
 "tips": ["2-3 practical, specific prep tips"],
 "confidence": "high|medium|low"}"""


def role_brief(user_id: str, target: dict, refresh: bool = False) -> dict:
    role = target.get("role_family") or "software_engineering"
    level = target.get("level") or ("intern" if target.get("employment") == "internship" else "new_grad")
    ckey = target.get("company_key") or company_key(target.get("company", ""))
    cache_key = f"{ckey or (target.get('company') or 'general').lower()}|{role}|{level}|{','.join(target.get('rounds') or [])}"
    if not refresh and not target.get("job_description"):
        cached = get_brief(cache_key)
        if cached:
            return {**cached, "cached": True}

    info = COMPANIES.get(ckey) if ckey else None
    loop = target.get("rounds") or default_loop(role, level)
    evidence = []
    sources = list((info or {}).get("sources", []))
    if info:
        evidence.append(f"Company notes ({info['label']}): {info['summary']}")
        note = info.get("notes", {}).get(role)
        if note:
            evidence.append(f"Role notes: {note}")
        evidence.append("Values: " + "; ".join(info.get("values", [])))
    company_name = target.get("company") or (info or {}).get("label", "")
    role_label = target.get("role_title") or ROLE_FAMILIES.get(role, {}).get("label", role)
    level_label = LEVELS.get(level, {}).get("label", level)
    search_used = False
    if company_name:
        results = web_search(f"{company_name} {role_label} {level_label} interview process rounds questions 2026")
        if results:
            search_used = True
            for r in results[:5]:
                evidence.append(f"Search: {r['title']} — {r['snippet']}")
                if r["url"] and all(s.get("url") != r["url"] for s in sources):
                    sources.append({"label": r["title"][:90] or r["url"], "url": r["url"], "kind": "web_search"})

    fallback = {
        "summary": (info or {}).get("summary") or f"A typical {level_label.lower()} {role_label} loop: " + ", ".join(ROUNDS[r]["label"] for r in loop) + ".",
        "loop": [{"round": r, "focus": ROUNDS[r]["assesses"]} for r in loop],
        "look_for": (info or {}).get("values", [])[:4] or ["Clear structure", "Specific evidence", "Sound trade-offs"],
        "tips": [LEVELS.get(level, {}).get("expectation", "")],
        "confidence": "medium" if info else "low",
    }
    brief = dict(fallback)
    try:
        prompt = (
            f"Target: {company_name or 'no specific company'} — {role_label} — {level_label} — "
            f"{'internship' if target.get('employment') == 'internship' else 'full-time'}\n"
            f"Allowed round keys: {', '.join(ROUNDS)}\n"
            f"Default loop for this role/level: {', '.join(loop)}\n"
            f"Level expectation: {LEVELS.get(level, {}).get('expectation', '')}\n"
            f"User focus: {target.get('focus', '')}\n"
            f"Job description excerpt: {clip(target.get('job_description', ''), 1500)}\n\nEvidence:\n" + "\n".join(evidence)
        )
        result = ask_json(user_id, "role_brief", prompt, system=BRIEF_SYSTEM, effort="medium", max_tokens=1200, temperature=0.2)
        rounds = [x for x in result.get("loop", []) if isinstance(x, dict) and x.get("round") in ROUNDS]
        if rounds:
            brief["loop"] = rounds[:6]
        if target.get("rounds"):
            # The user asked for specific rounds: practise those, keep the real loop for context.
            focus = {x["round"]: x.get("focus", "") for x in rounds}
            brief["full_loop"] = [x["round"] for x in rounds]
            brief["loop"] = [{"round": r, "focus": focus.get(r) or ROUNDS[r]["assesses"]} for r in target["rounds"]]
        for key in ("summary", "confidence"):
            if isinstance(result.get(key), str) and result[key]:
                brief[key] = result[key][:600]
        for key in ("look_for", "tips"):
            if isinstance(result.get(key), list) and result[key]:
                brief[key] = [str(x)[:200] for x in result[key]][:5]
    except Exception:
        pass

    for item in brief["loop"]:
        meta = ROUNDS[item["round"]]
        item["label"] = meta["label"]
        item["minutes"] = meta["minutes"]
    brief.update({
        "company": company_name,
        "role_label": role_label,
        "level_label": level_label,
        "level_expectation": LEVELS.get(level, {}).get("expectation", ""),
        "sources": sources[:8],
        "search_used": search_used,
        "cached": False,
    })
    if not target.get("job_description"):
        save_brief(cache_key, brief)
    return brief


# ---------------------------------------------------------------- resume digest

DIGEST_SYSTEM = """Summarise a resume for an interviewer who will ask deep-dive questions. Return only JSON:
{"headline": "one line: who this person is professionally",
 "experience_level": "student|new_grad|early_career|experienced",
 "skills": ["up to 12 concrete skills"],
 "projects": [{"name": "...", "summary": "one sentence", "tech": ["..."], "claims": ["measurable claims made, verbatim numbers"], "probe": ["2-3 questions an interviewer would ask to test real ownership"]}],
 "gaps": ["up to 3 areas the resume leaves unclear"]}
Up to 5 projects or roles, most impressive first. Omit contact details, addresses and personal data."""


def digest_resume(user_id: str, refresh: bool = False) -> dict | None:
    if not refresh:
        cached = resume_digest(user_id)
        if cached:
            return cached
    resume = resume_for_user(user_id)
    text = (resume or {}).get("extracted_text", "")
    if not text.strip():
        return None
    try:
        digest = ask_json(user_id, "resume_digest", clip(text, 9000), system=DIGEST_SYSTEM, effort="low", max_tokens=1500, temperature=0)
    except Exception:
        return None
    save_resume_digest(user_id, digest)
    return digest
