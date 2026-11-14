"""Long-term coaching memory.

What is remembered (and why):
- growth      A recurring gap tied to a competency ("answers lack measurable results").
              Drives which skills the next interview probes.
- strength    Something the candidate reliably does well. Lets the interviewer move
              faster through solved ground.
- story       A STAR story the candidate has used (title + one line). Prevents the
              interviewer asking for the same story twice and lets it probe deeper.
- fact        Career context the candidate stated (target roles, background, years).
- preference  How the candidate wants to practise ("prefers typed answers").

What is never remembered:
- Raw audio or full transcripts (those live only in interview history, which the
  user can delete).
- Sensitive personal data: health, religion, politics, immigration status, family
  plans, age, ethnicity, salary numbers, contact details.
- Personality judgements ("nervous person") and one-off slips seen only once with
  low confidence; these stay as `candidate` and expire if not seen again.

Lifecycle: candidate -> active (seen twice or high confidence) -> resolved
(improvement confirmed on spaced reviews: 1, 3, 7, 14, 30 days). Only a small,
prioritised slice of memory goes into any prompt.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from storage import connection, now_iso

KINDS = ("growth", "strength", "story", "fact", "preference")
REVIEW_DAYS = (1, 3, 7, 14, 30)
RESOLVE_AT_STAGE = 3
CANDIDATE_TTL_DAYS = 45
PROMPT_BUDGET = 6
MAX_CONTENT = 220
MAX_TITLE = 80

SENSITIVE = re.compile(
    r"\b(pregnan\w*|diagnos\w*|disab\w*|depress\w*|anxiety disorder|adhd|autis\w*|religio\w*|"
    r"church|mosque|politic\w*|visa status|immigra\w*|green card|citizenship|ethnic\w*|race\b|"
    r"sexual\w*|salary of|\$\s?\d{2,3},?\d{3}|phone number|home address|ssn|social security|"
    r"married|divorc\w*|my age|years old)\b",
    re.IGNORECASE,
)
JUDGEMENT = re.compile(r"\b(lazy|stupid|dumb|arrogant|weird|annoying|unlikable)\b", re.IGNORECASE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _due(stage: int) -> str:
    days = REVIEW_DAYS[min(stage, len(REVIEW_DAYS) - 1)]
    return (_now() + timedelta(days=days)).isoformat()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def _similar(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def allowed(item: dict) -> bool:
    """Policy gate applied to every memory the model proposes."""
    kind = item.get("kind")
    text = f"{item.get('title', '')} {item.get('content', '')}"
    if kind not in KINDS or not item.get("content"):
        return False
    if SENSITIVE.search(text) or JUDGEMENT.search(text):
        return False
    return len(text.strip()) >= 12


def remember(user_id: str, items: list[dict], session_id: str = "", answer_id: int | None = None) -> list[int]:
    """Store proposed memories after policy filtering and fuzzy de-duplication."""
    saved: list[int] = []
    for raw in items or []:
        if not isinstance(raw, dict) or not allowed(raw):
            continue
        kind = raw["kind"]
        topic = str(raw.get("topic") or "")[:40]
        title = str(raw.get("title") or raw["content"])[:MAX_TITLE].strip()
        content = str(raw["content"])[:MAX_CONTENT].strip()
        evidence = str(raw.get("evidence") or "")[:240].strip()
        confidence = max(0.2, min(0.95, float(raw.get("confidence") or 0.6)))
        saved_id = _merge_or_insert(user_id, kind, topic, title, content, evidence, confidence, answer_id)
        if saved_id:
            saved.append(saved_id)
    return saved


def _merge_or_insert(user_id, kind, topic, title, content, evidence, confidence, answer_id) -> int:
    now = now_iso()
    with connection() as db:
        rows = db.execute(
            """SELECT id,title,content,times_seen,confidence,status FROM memory_items
               WHERE user_id=? AND kind=? AND (topic=? OR ?='') AND status!='archived'""",
            (user_id, kind, topic, topic),
        ).fetchall()
        best, best_score = None, 0.0
        for row in rows:
            score = max(_similar(title, row["title"] or row["content"]), _similar(content, row["content"]))
            if score > best_score:
                best, best_score = row, score
        if best is not None and best_score >= 0.45:
            seen = best["times_seen"] + 1
            status = best["status"]
            if kind == "growth" and status == "resolved":
                status = "active"  # regression: the gap came back
            elif status == "candidate" and (seen >= 2 or confidence >= 0.8):
                status = "active"
            db.execute(
                """UPDATE memory_items SET times_seen=?, last_seen=?, status=?,
                   confidence=MIN(0.95, MAX(confidence, ?) + 0.05),
                   evidence=CASE WHEN ?!='' THEN ? ELSE evidence END,
                   content=CASE WHEN LENGTH(?)>=LENGTH(content) THEN ? ELSE content END,
                   review_stage=CASE WHEN ?='growth' THEN 0 ELSE review_stage END,
                   next_review_at=CASE WHEN ?='growth' THEN ? ELSE next_review_at END
                   WHERE id=?""",
                (seen, now, status, confidence, evidence, evidence, content, content,
                 kind, kind, _due(0), best["id"]),
            )
            return int(best["id"])
        status = "active" if confidence >= 0.8 or kind in ("fact", "preference", "story") else "candidate"
        try:
            cursor = db.execute(
                """INSERT INTO memory_items(user_id,kind,topic,content,confidence,status,
                   source_answer_id,first_seen,last_seen,next_review_at,evidence,review_stage,title)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,0,?)""",
                (user_id, kind, topic, content, confidence, status, answer_id, now, now,
                 _due(0) if kind == "growth" else None, evidence, title),
            )
            return int(cursor.lastrowid or 0)
        except Exception:
            return 0


def record_review(user_id: str, competency: str, score: float) -> None:
    """Advance or reset spaced review for growth items on this competency."""
    if not competency:
        return
    with connection() as db:
        rows = db.execute(
            """SELECT id, review_stage FROM memory_items WHERE user_id=? AND kind='growth'
               AND topic=? AND status IN ('active','candidate')""",
            (user_id, competency),
        ).fetchall()
        for row in rows:
            if score >= 4:
                stage = row["review_stage"] + 1
                status = "resolved" if stage >= RESOLVE_AT_STAGE else "active"
                db.execute(
                    "UPDATE memory_items SET review_stage=?, status=?, next_review_at=?, last_seen=? WHERE id=?",
                    (stage, status, _due(stage), now_iso(), row["id"]),
                )
            elif score <= 2.5:
                db.execute(
                    "UPDATE memory_items SET review_stage=0, next_review_at=?, times_seen=times_seen+1, last_seen=? WHERE id=?",
                    (_due(0), now_iso(), row["id"]),
                )


def expire_candidates(user_id: str) -> None:
    cutoff = (_now() - timedelta(days=CANDIDATE_TTL_DAYS)).isoformat()
    with connection() as db:
        db.execute(
            "UPDATE memory_items SET status='archived' WHERE user_id=? AND status='candidate' AND last_seen<?",
            (user_id, cutoff),
        )


def _active(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT id,kind,topic,title,content,confidence,times_seen,status,review_stage,
               next_review_at,last_seen FROM memory_items
               WHERE user_id=? AND status IN ('active','candidate') AND is_demo=0""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def focus_competencies(user_id: str, limit: int = 3) -> list[str]:
    """Competencies whose growth items are due, most important first."""
    now = now_iso()
    growth = [m for m in _active(user_id) if m["kind"] == "growth" and m["topic"]]
    growth.sort(key=lambda m: (
        0 if (m["next_review_at"] or "") <= now else 1,
        0 if m["status"] == "active" else 1,
        -m["times_seen"],
        -m["confidence"],
    ))
    seen: list[str] = []
    for item in growth:
        if item["topic"] not in seen:
            seen.append(item["topic"])
    return seen[:limit]


def memory_brief(user_id: str, competencies: list[str] | None = None, budget: int = PROMPT_BUDGET) -> str:
    """A few short lines of memory relevant to this session, within a fixed budget."""
    items = _active(user_id)
    if not items:
        return ""
    now = now_iso()
    wanted = set(competencies or [])

    def rank(m: dict) -> tuple:
        due = m["kind"] == "growth" and (m["next_review_at"] or "") <= now
        kind_order = {"growth": 0, "story": 1, "preference": 2, "fact": 3, "strength": 4}[m["kind"]]
        relevant = 0 if (m["topic"] in wanted or not wanted) else 1
        return (0 if due else 1, relevant, kind_order, 0 if m["status"] == "active" else 1, -m["times_seen"])

    items.sort(key=rank)
    lines = []
    for m in items[:budget]:
        label = {"growth": "Work on", "strength": "Strength", "story": "Story used", "fact": "Context", "preference": "Prefers"}[m["kind"]]
        topic = f" [{m['topic']}]" if m["topic"] else ""
        seen = f" (seen {m['times_seen']}x)" if m["times_seen"] > 1 else ""
        lines.append(f"- {label}{topic}: {m['content'][:150]}{seen}")
    return "\n".join(lines)


def used_story_titles(user_id: str) -> list[str]:
    return [m["title"] or m["content"][:60] for m in _active(user_id) if m["kind"] == "story"][:12]


# ---------------------------------------------------------------- user-facing CRUD


def list_memory(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT id,kind,topic,title,content,evidence,confidence,times_seen,status,
               review_stage,next_review_at,first_seen,last_seen FROM memory_items
               WHERE user_id=? AND status!='archived' AND is_demo=0
               ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'candidate' THEN 1 ELSE 2 END,
               last_seen DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def edit_memory(user_id: str, memory_id: int, fields: dict) -> bool:
    updates, values = [], []
    if "content" in fields:
        content = str(fields["content"])[:MAX_CONTENT].strip()
        if not content:
            return False
        updates.append("content=?")
        values.append(content)
    if "title" in fields:
        updates.append("title=?")
        values.append(str(fields["title"])[:MAX_TITLE])
    if fields.get("status") in ("active", "resolved", "archived"):
        updates.append("status=?")
        values.append(fields["status"])
    if not updates:
        return False
    with connection() as db:
        cursor = db.execute(
            f"UPDATE memory_items SET {', '.join(updates)} WHERE id=? AND user_id=?",
            (*values, memory_id, user_id),
        )
        return cursor.rowcount > 0


def add_memory(user_id: str, kind: str, content: str, topic: str = "") -> int:
    ids = remember(user_id, [{"kind": kind, "content": content, "topic": topic, "confidence": 0.9}])
    return ids[0] if ids else 0


def delete_memory(user_id: str, memory_id: int) -> bool:
    with connection() as db:
        cursor = db.execute("DELETE FROM memory_items WHERE id=? AND user_id=?", (memory_id, user_id))
        return cursor.rowcount > 0


def clear_memory(user_id: str) -> int:
    with connection() as db:
        cursor = db.execute("DELETE FROM memory_items WHERE user_id=? AND is_demo=0", (user_id,))
        return cursor.rowcount
