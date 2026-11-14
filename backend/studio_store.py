"""SQLite persistence for the interview studio: profiles, question bank, role
briefs, durable interview state and model-usage accounting.

Every schema change here is additive (new tables or new nullable columns), so
an existing production database upgrades in place on startup.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Iterable

from storage import connection, now_iso

DEFAULT_PREFS = {
    "persona": "maya",
    "voice": "auto",
    "pressure": "realistic",
    "answer_mode": "voice",
    "auto_listen": False,
    "show_captions": True,
    "memory_enabled": True,
    "speak_feedback": True,
}


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_columns(db: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _columns(db, table)
    for name, definition in columns.items():
        if name not in existing:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_studio(db: sqlite3.Connection) -> None:
    """Create studio tables and extend legacy ones; safe to run repeatedly."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            prefs_json TEXT NOT NULL DEFAULT '{}',
            target_json TEXT NOT NULL DEFAULT '{}',
            onboarding_done INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT '',
            purpose TEXT NOT NULL,
            provider TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS question_bank (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            kind TEXT NOT NULL,
            role_families TEXT NOT NULL DEFAULT '[]',
            levels TEXT NOT NULL DEFAULT '[]',
            companies TEXT NOT NULL DEFAULT '[]',
            competencies TEXT NOT NULL DEFAULT '[]',
            difficulty INTEGER NOT NULL DEFAULT 2,
            rubric TEXT NOT NULL DEFAULT '[]',
            followups TEXT NOT NULL DEFAULT '[]',
            pitfalls TEXT NOT NULL DEFAULT '[]',
            provenance TEXT NOT NULL DEFAULT 'practice',
            source_note TEXT NOT NULL DEFAULT '',
            source_urls TEXT NOT NULL DEFAULT '[]',
            priority REAL NOT NULL DEFAULT 0.5,
            status TEXT NOT NULL DEFAULT 'active',
            times_reported INTEGER NOT NULL DEFAULT 1,
            last_reported TEXT,
            origin TEXT NOT NULL DEFAULT 'seed',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS role_briefs (
            cache_key TEXT PRIMARY KEY,
            brief_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_usage_user ON llm_usage(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_bank_kind ON question_bank(kind, status);
        """
    )
    _add_columns(
        db,
        "users",
        {
            "auth_provider": "TEXT NOT NULL DEFAULT 'password'",
            "google_sub": "TEXT",
            "avatar_url": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _add_columns(
        db,
        "interviews",
        {
            "target_json": "TEXT NOT NULL DEFAULT '{}'",
            "plan_json": "TEXT NOT NULL DEFAULT '[]'",
            "state_json": "TEXT NOT NULL DEFAULT '{}'",
            "report_json": "TEXT NOT NULL DEFAULT ''",
            "persona": "TEXT NOT NULL DEFAULT ''",
            "title": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _add_columns(
        db,
        "answers",
        {
            "assessment_json": "TEXT NOT NULL DEFAULT '{}'",
            "code_text": "TEXT NOT NULL DEFAULT ''",
            "question_id": "TEXT NOT NULL DEFAULT ''",
            "exchange_kind": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _add_columns(
        db,
        "memory_items",
        {
            "evidence": "TEXT NOT NULL DEFAULT ''",
            "review_stage": "INTEGER NOT NULL DEFAULT 0",
            "title": "TEXT NOT NULL DEFAULT ''",
        },
    )
    _add_columns(db, "resumes", {"digest_json": "TEXT NOT NULL DEFAULT ''"})
    _add_columns(db, "question_bank", {"extras": "TEXT NOT NULL DEFAULT '{}'"})
    db.execute(
        """CREATE TABLE IF NOT EXISTS trending_problems (
            company TEXT NOT NULL,
            ref TEXT NOT NULL,
            title TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT '',
            frequency REAL NOT NULL DEFAULT 0,
            topics TEXT NOT NULL DEFAULT '',
            window TEXT NOT NULL DEFAULT '30d',
            source TEXT NOT NULL DEFAULT '',
            fetched_at TEXT NOT NULL,
            PRIMARY KEY(company, ref)
        )"""
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL"
    )


# ---------------------------------------------------------------- profiles


def get_profile(user_id: str) -> dict:
    with connection() as db:
        row = db.execute("SELECT * FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
    prefs = dict(DEFAULT_PREFS)
    target: dict = {}
    onboarding_done = False
    if row:
        prefs.update(_loads(row["prefs_json"], {}))
        target = _loads(row["target_json"], {})
        onboarding_done = bool(row["onboarding_done"])
    return {"prefs": prefs, "target": target, "onboarding_done": onboarding_done}


def save_profile(
    user_id: str,
    prefs: dict | None = None,
    target: dict | None = None,
    onboarding_done: bool | None = None,
) -> dict:
    current = get_profile(user_id)
    if prefs:
        current["prefs"].update({k: v for k, v in prefs.items() if k in DEFAULT_PREFS})
    if target is not None:
        current["target"] = target
    if onboarding_done is not None:
        current["onboarding_done"] = onboarding_done
    with connection() as db:
        db.execute(
            """INSERT INTO user_profiles(user_id,prefs_json,target_json,onboarding_done,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
               prefs_json=excluded.prefs_json,target_json=excluded.target_json,
               onboarding_done=excluded.onboarding_done,updated_at=excluded.updated_at""",
            (
                user_id,
                json.dumps(current["prefs"]),
                json.dumps(current["target"]),
                int(current["onboarding_done"]),
                now_iso(),
            ),
        )
    return current


# ---------------------------------------------------------------- usage


def log_usage(
    user_id: str, session_id: str, purpose: str, provider: str, usage: dict
) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO llm_usage(user_id,session_id,purpose,provider,prompt_tokens,
               completion_tokens,cached_tokens,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user_id,
                session_id or "",
                purpose,
                provider,
                int(usage.get("prompt_tokens", 0)),
                int(usage.get("completion_tokens", 0)),
                int(usage.get("cached_tokens", 0)),
                now_iso(),
            ),
        )


def usage_summary(user_id: str, session_id: str = "") -> dict:
    with connection() as db:
        row = db.execute(
            """SELECT COUNT(*) AS calls, COALESCE(SUM(prompt_tokens),0) AS prompt,
               COALESCE(SUM(completion_tokens),0) AS completion,
               COALESCE(SUM(cached_tokens),0) AS cached
               FROM llm_usage WHERE user_id=? AND (?='' OR session_id=?)""",
            (user_id, session_id, session_id),
        ).fetchone()
    return {
        "calls": row["calls"],
        "prompt_tokens": row["prompt"],
        "completion_tokens": row["completion"],
        "cached_tokens": row["cached"],
    }


# ---------------------------------------------------------------- question bank

_JSON_FIELDS = ("role_families", "levels", "companies", "competencies", "rubric", "followups", "pitfalls", "source_urls")


def upsert_questions(questions: Iterable[dict], origin: str = "seed") -> int:
    """Insert or refresh bank entries. Seed refreshes keep report counts."""
    count = 0
    now = now_iso()
    with connection() as db:
        for q in questions:
            values = {
                "id": q["id"],
                "text": q["text"],
                "kind": q["kind"],
                "difficulty": int(q.get("difficulty", 2)),
                "provenance": q.get("provenance", "practice"),
                "source_note": q.get("source_note", ""),
                "priority": float(q.get("priority", 0.5)),
                "status": q.get("status", "active"),
                "extras": json.dumps(q.get("extras", {})),
                **{field: json.dumps(q.get(field, [])) for field in _JSON_FIELDS},
            }
            db.execute(
                f"""INSERT INTO question_bank(id,text,kind,{",".join(_JSON_FIELDS)},difficulty,
                    provenance,source_note,priority,status,origin,last_reported,created_at,updated_at,extras)
                    VALUES(:id,:text,:kind,{",".join(":" + f for f in _JSON_FIELDS)},:difficulty,
                    :provenance,:source_note,:priority,:status,:origin,:now,:now,:now,:extras)
                    ON CONFLICT(id) DO UPDATE SET text=excluded.text,kind=excluded.kind,
                    {",".join(f"{f}=excluded.{f}" for f in _JSON_FIELDS)},
                    difficulty=excluded.difficulty,provenance=excluded.provenance,
                    source_note=excluded.source_note,extras=excluded.extras,
                    priority=MAX(question_bank.priority, excluded.priority),
                    updated_at=excluded.updated_at""",
                {**values, "origin": origin, "now": now},
            )
            count += 1
    return count


def _question_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    for field in _JSON_FIELDS:
        item[field] = _loads(item[field], [])
    item["extras"] = _loads(item.get("extras"), {})
    return item


def list_questions(kinds: Iterable[str] | None = None, status: str = "active") -> list[dict]:
    kinds = list(kinds or [])
    with connection() as db:
        if kinds:
            marks = ",".join("?" for _ in kinds)
            rows = db.execute(
                f"SELECT * FROM question_bank WHERE status=? AND kind IN ({marks})",
                (status, *kinds),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM question_bank WHERE status=?", (status,)).fetchall()
    return [_question_row(row) for row in rows]


def get_question(question_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT * FROM question_bank WHERE id=?", (question_id,)).fetchone()
    return _question_row(row) if row else None


def question_bank_stats() -> dict:
    with connection() as db:
        rows = db.execute(
            """SELECT kind, provenance, status, COUNT(*) AS total FROM question_bank
               GROUP BY kind, provenance, status"""
        ).fetchall()
    return {"groups": [dict(row) for row in rows]}


def user_question_history(user_id: str, limit: int = 200) -> dict[str, dict]:
    """Map question ids to the user's latest outcome for spacing and repetition."""
    with connection() as db:
        rows = db.execute(
            """SELECT question_id, MAX(created_at) AS last_asked, COUNT(*) AS times,
               AVG(score) AS avg_score FROM answers
               WHERE user_id=? AND question_id!='' AND relevance!='mismatch'
               GROUP BY question_id ORDER BY last_asked DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return {row["question_id"]: dict(row) for row in rows}


# ---------------------------------------------------------------- role briefs


def get_brief(cache_key: str, max_age_days: int = 21) -> dict | None:
    with connection() as db:
        row = db.execute(
            """SELECT brief_json FROM role_briefs WHERE cache_key=?
               AND created_at > datetime('now', ?)""",
            (cache_key, f"-{int(max_age_days)} days"),
        ).fetchone()
    return _loads(row["brief_json"], None) if row else None


def save_brief(cache_key: str, brief: dict) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO role_briefs(cache_key,brief_json,created_at) VALUES(?,?,datetime('now'))
               ON CONFLICT(cache_key) DO UPDATE SET brief_json=excluded.brief_json,
               created_at=excluded.created_at""",
            (cache_key, json.dumps(brief)),
        )


# ---------------------------------------------------------------- interviews


def create_studio_interview(
    session_id: str,
    user_id: str,
    target: dict,
    plan: list,
    state: dict,
    persona: str,
    title: str,
    duration_minutes: int,
) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO interviews(session_id,user_id,mode,topic,job_description,
               duration_minutes,created_at,target_json,plan_json,state_json,persona,title)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id,
                user_id,
                "studio",
                target.get("round", ""),
                target.get("job_description", "")[:4000],
                duration_minutes,
                now_iso(),
                json.dumps(target),
                json.dumps(plan),
                json.dumps(state),
                persona,
                title,
            ),
        )


def save_studio_state(session_id: str, state: dict, plan: list | None = None) -> None:
    with connection() as db:
        if plan is None:
            db.execute(
                "UPDATE interviews SET state_json=?, cumulative_summary=? WHERE session_id=?",
                (json.dumps(state), state.get("notes", ""), session_id),
            )
        else:
            db.execute(
                "UPDATE interviews SET state_json=?, plan_json=?, cumulative_summary=? WHERE session_id=?",
                (json.dumps(state), json.dumps(plan), state.get("notes", ""), session_id),
            )


def load_studio_interview(session_id: str, user_id: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM interviews WHERE session_id=? AND user_id=? AND mode='studio'",
            (session_id, user_id),
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["target"] = _loads(item.pop("target_json"), {})
    item["plan"] = _loads(item.pop("plan_json"), [])
    item["state"] = _loads(item.pop("state_json"), {})
    item["report"] = _loads(item.pop("report_json"), None) if item.get("report_json") else None
    return item


def save_studio_report(session_id: str, report: dict, overall_score: float) -> None:
    with connection() as db:
        db.execute(
            """UPDATE interviews SET report_json=?, status='completed', overall_score=?,
               completed_at=COALESCE(completed_at, ?) WHERE session_id=?""",
            (json.dumps(report), overall_score, now_iso(), session_id),
        )


def save_exchange(user_id: str, session_id: str, exchange: dict) -> int:
    assessment = exchange.get("assessment") or {}
    with connection() as db:
        cursor = db.execute(
            """INSERT INTO answers(session_id,user_id,question_number,question,answer,topic,
               score,strengths,improvements,dimension_scores,created_at,assessment_json,
               code_text,question_id,exchange_kind)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(session_id,question_number) DO UPDATE SET answer=excluded.answer,
               score=excluded.score,assessment_json=excluded.assessment_json,
               code_text=excluded.code_text""",
            (
                session_id,
                user_id,
                exchange["number"],
                exchange["question"],
                exchange["answer"],
                exchange.get("topic", ""),
                float(assessment.get("score") or 0),
                "; ".join(assessment.get("strengths", []) or []),
                "; ".join(assessment.get("missing", []) or []),
                json.dumps(assessment.get("dimensions", {})),
                now_iso(),
                json.dumps(assessment),
                exchange.get("code", ""),
                exchange.get("question_id", ""),
                exchange.get("kind", ""),
            ),
        )
        return int(cursor.lastrowid or 0)


def list_studio_interviews(user_id: str, limit: int = 50) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT i.session_id,i.title,i.persona,i.status,i.overall_score,i.created_at,
               i.completed_at,i.duration_minutes,i.target_json,i.report_json,
               COUNT(a.id) AS exchanges
               FROM interviews i LEFT JOIN answers a ON a.session_id=i.session_id
               WHERE i.user_id=? AND i.mode='studio' AND i.status!='cancelled'
               GROUP BY i.session_id ORDER BY i.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["target"] = _loads(item.pop("target_json"), {})
        report = _loads(item.pop("report_json"), None) if row["report_json"] else None
        item["verdict"] = (report or {}).get("overall", {}).get("verdict", "")
        item["headline"] = (report or {}).get("overall", {}).get("headline", "")
        items.append(item)
    return items


def studio_exchanges(user_id: str, session_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT question_number,question,answer,score,assessment_json,code_text,
               question_id,exchange_kind,relevance FROM answers
               WHERE session_id=? AND user_id=? ORDER BY question_number""",
            (session_id, user_id),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["assessment"] = _loads(item.pop("assessment_json"), {})
        result.append(item)
    return result


# ---------------------------------------------------------------- resume digest


def save_resume_digest(user_id: str, digest: dict) -> None:
    with connection() as db:
        db.execute(
            "UPDATE resumes SET digest_json=? WHERE user_id=?", (json.dumps(digest), user_id)
        )


def resume_digest(user_id: str) -> dict | None:
    with connection() as db:
        row = db.execute("SELECT digest_json FROM resumes WHERE user_id=?", (user_id,)).fetchone()
    if not row or not row["digest_json"]:
        return None
    return _loads(row["digest_json"], None)


# ---------------------------------------------------------------- helpers


def _loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------- accounts


def google_user(sub: str, email: str, name: str = "", picture: str = "") -> dict:
    """Find or create the account for a verified Google identity.

    An existing email/password account with the same verified email is linked
    rather than duplicated."""
    import secrets
    import uuid

    email = email.strip().lower()
    with connection() as db:
        row = db.execute("SELECT * FROM users WHERE google_sub=?", (sub,)).fetchone()
        if not row:
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if row:
                db.execute(
                    "UPDATE users SET google_sub=?, avatar_url=?, name=CASE WHEN name='' THEN ? ELSE name END WHERE id=?",
                    (sub, picture, name, row["id"]),
                )
            else:
                user_id = uuid.uuid4().hex
                db.execute(
                    """INSERT INTO users(id,email,password_hash,name,created_at,auth_provider,google_sub,avatar_url)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (user_id, email, "!google:" + secrets.token_hex(8), name, now_iso(), "google", sub, picture),
                )
            row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def account_info(user_id: str) -> dict:
    with connection() as db:
        row = db.execute(
            "SELECT id,email,name,created_at,auth_provider,google_sub,avatar_url,password_hash FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        sessions = db.execute(
            "SELECT COUNT(*) AS n FROM auth_tokens WHERE user_id=? AND expires_at>?", (user_id, now_iso())
        ).fetchone()["n"]
        interviews = db.execute(
            "SELECT COUNT(*) AS n FROM interviews WHERE user_id=? AND mode='studio' AND status='completed'", (user_id,)
        ).fetchone()["n"]
    if not row:
        return {}
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "created_at": row["created_at"],
        "avatar_url": row["avatar_url"],
        "google_linked": bool(row["google_sub"]),
        "has_password": not str(row["password_hash"]).startswith("!"),
        "active_sessions": sessions,
        "completed_interviews": interviews,
    }


def update_name(user_id: str, name: str) -> None:
    with connection() as db:
        db.execute("UPDATE users SET name=? WHERE id=?", (name.strip()[:80], user_id))


def set_password(user_id: str, new_password: str) -> None:
    from storage import _password_hash

    if len(new_password) < 8:
        raise ValueError("Use at least 8 characters")
    with connection() as db:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (_password_hash(new_password), user_id))


def revoke_tokens(user_id: str, keep_token_hash: str = "") -> int:
    with connection() as db:
        cursor = db.execute(
            "DELETE FROM auth_tokens WHERE user_id=? AND token_hash!=?", (user_id, keep_token_hash)
        )
        return cursor.rowcount


def delete_account(user_id: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM users WHERE id=?", (user_id,))
        for table in ("user_profiles", "llm_usage"):
            db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))


def delete_studio_interview(user_id: str, session_id: str) -> bool:
    with connection() as db:
        db.execute("DELETE FROM answers WHERE session_id=? AND user_id=?", (session_id, user_id))
        cursor = db.execute("DELETE FROM interviews WHERE session_id=? AND user_id=?", (session_id, user_id))
        return cursor.rowcount > 0


def export_user_data(user_id: str) -> dict:
    with connection() as db:
        memory = [dict(r) for r in db.execute(
            "SELECT kind,topic,title,content,status,first_seen,last_seen FROM memory_items WHERE user_id=?", (user_id,)
        ).fetchall()]
    return {
        "account": {k: v for k, v in account_info(user_id).items() if k != "id"},
        "profile": get_profile(user_id),
        "interviews": [
            {**item, "exchanges": studio_exchanges(user_id, item["session_id"])}
            for item in list_studio_interviews(user_id, 500)
        ],
        "memory": memory,
    }


# ---------------------------------------------------------------- trending problems


def save_trending(company: str, rows: list[dict], source: str) -> int:
    """Replace a company's recently-reported list with a fresh snapshot."""
    now = now_iso()
    with connection() as db:
        db.execute("DELETE FROM trending_problems WHERE company=?", (company,))
        for row in rows:
            db.execute(
                """INSERT OR REPLACE INTO trending_problems(company,ref,title,difficulty,frequency,topics,window,source,fetched_at)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (company, row["ref"], row["title"], row.get("difficulty", ""), float(row.get("frequency", 0)),
                 row.get("topics", ""), row.get("window", "30d"), source, now),
            )
    return len(rows)


def trending_for(company: str = "") -> dict[str, float]:
    """ref -> recency score (0-1). Without a company, the average across companies."""
    with connection() as db:
        if company:
            rows = db.execute("SELECT ref, frequency FROM trending_problems WHERE company=?", (company,)).fetchall()
            return {r["ref"]: r["frequency"] / 100 for r in rows}
        rows = db.execute(
            "SELECT ref, SUM(frequency) AS f, COUNT(DISTINCT company) AS c FROM trending_problems GROUP BY ref"
        ).fetchall()
        total = db.execute("SELECT COUNT(DISTINCT company) AS c FROM trending_problems").fetchone()["c"] or 1
    return {r["ref"]: min(1.0, r["f"] / 100 / max(1, total) * 2) for r in rows}


def trending_summary(company: str, limit: int = 8) -> dict:
    with connection() as db:
        rows = db.execute(
            "SELECT title, difficulty, frequency, topics, fetched_at FROM trending_problems WHERE company=? ORDER BY frequency DESC LIMIT 60",
            (company,),
        ).fetchall()
    if not rows:
        return {}
    topics: dict[str, float] = {}
    for r in rows:
        for t in [x.strip() for x in r["topics"].split(",") if x.strip()]:
            topics[t] = topics.get(t, 0) + r["frequency"]
    mix = {}
    for r in rows:
        mix[r["difficulty"].title()] = mix.get(r["difficulty"].title(), 0) + 1
    return {
        "topics": [t for t, _ in sorted(topics.items(), key=lambda kv: -kv[1])[:limit]],
        "difficulty_mix": mix,
        "count": len(rows),
        "fetched_at": rows[0]["fetched_at"],
    }


def trending_age_days() -> float | None:
    with connection() as db:
        row = db.execute("SELECT MAX(fetched_at) AS t FROM trending_problems").fetchone()
    if not row or not row["t"]:
        return None
    from datetime import datetime, timezone

    return (datetime.now(timezone.utc) - datetime.fromisoformat(row["t"])).total_seconds() / 86400
