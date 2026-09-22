"""Local SQLite persistence for accounts, resumes, interview history, and memory."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = Path(os.getenv("AI_INTERVIEWER_DB", DATA_DIR / "interviewer.db"))
PASSWORD_ITERATIONS = 260_000
SECRET_KEY_PATH = DATA_DIR / ".secret_key"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _cipher() -> Fernet:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.write_bytes(Fernet.generate_key())
        SECRET_KEY_PATH.chmod(0o600)
    return Fernet(SECRET_KEY_PATH.read_bytes().strip())


def init_db() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resumes (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                filename TEXT NOT NULL,
                pdf BLOB NOT NULL,
                extracted_text TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS interviews (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                mode TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                job_description TEXT NOT NULL DEFAULT '',
                duration_minutes INTEGER NOT NULL,
                cumulative_summary TEXT NOT NULL DEFAULT '',
                overall_score REAL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES interviews(session_id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                question_number INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                score REAL NOT NULL DEFAULT 0,
                strengths TEXT NOT NULL DEFAULT '',
                improvements TEXT NOT NULL DEFAULT '',
                relevance TEXT NOT NULL DEFAULT 'pending',
                issue_type TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(session_id, question_number)
            );

            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.6,
                times_seen INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'active',
                source_answer_id INTEGER REFERENCES answers(id) ON DELETE SET NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                next_review_at TEXT,
                UNIQUE(user_id, kind, topic, content)
            );

            CREATE TABLE IF NOT EXISTS user_topics (
                key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                UNIQUE(user_id, name)
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                encrypted_key BLOB NOT NULL,
                last_four TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, provider)
            );

            CREATE INDEX IF NOT EXISTS idx_answers_user_topic
                ON answers(user_id, topic, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_user_status
                ON memory_items(user_id, status, next_review_at);
            """
        )


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"{PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def _password_valid(password: str, encoded: str) -> bool:
    try:
        iterations, salt, expected = encoded.split("$", 2)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return secrets.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def _public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


def create_user(email: str, password: str, name: str = "") -> dict:
    email = email.strip().lower()
    if "@" not in email:
        raise ValueError("Please enter a valid email address")
    if len(password) < 6:
        raise ValueError("Password must contain at least 6 characters")
    user_id = uuid.uuid4().hex
    try:
        with connection() as db:
            db.execute(
                "INSERT INTO users(id,email,password_hash,name,created_at) VALUES(?,?,?,?,?)",
                (user_id, email, _password_hash(password), name.strip(), now_iso()),
            )
            row = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    except sqlite3.IntegrityError as exc:
        raise ValueError("An account with this email already exists") from exc
    return _public_user(row)


def authenticate_user(email: str, password: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        ).fetchone()
    return _public_user(row) if row and _password_valid(password, row["password_hash"]) else None


def issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    with connection() as db:
        db.execute(
            "INSERT INTO auth_tokens(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token_hash, user_id, expires_at, now_iso()),
        )
    return token


def user_for_token(token: str) -> dict | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connection() as db:
        row = db.execute(
            """SELECT users.* FROM auth_tokens
               JOIN users ON users.id=auth_tokens.user_id
               WHERE auth_tokens.token_hash=? AND auth_tokens.expires_at>?""",
            (token_hash, now_iso()),
        ).fetchone()
    return _public_user(row) if row else None


def save_resume(user_id: str, filename: str, pdf: bytes, extracted_text: str) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO resumes(user_id,filename,pdf,extracted_text,updated_at)
               VALUES(?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET filename=excluded.filename,
               pdf=excluded.pdf, extracted_text=excluded.extracted_text,
               updated_at=excluded.updated_at""",
            (user_id, filename, pdf, extracted_text, now_iso()),
        )


def resume_for_user(user_id: str, include_pdf: bool = False) -> dict | None:
    columns = "filename,extracted_text,updated_at" + (",pdf" if include_pdf else "")
    with connection() as db:
        row = db.execute(f"SELECT {columns} FROM resumes WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def delete_resume(user_id: str) -> bool:
    with connection() as db:
        result = db.execute("DELETE FROM resumes WHERE user_id=?", (user_id,))
    return result.rowcount > 0


def create_interview(record: dict) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO interviews(session_id,user_id,mode,topic,job_description,
               duration_minutes,created_at) VALUES(?,?,?,?,?,?,?)""",
            (
                record["session_id"], record["user_id"], record["mode"], record["topic"],
                record["job_description"], record["duration_minutes"], now_iso(),
            ),
        )


def save_answer(user_id: str, session_id: str, entry: dict, topic: str) -> int:
    evaluation = entry["evaluation"]
    with connection() as db:
        cursor = db.execute(
            """INSERT INTO answers(session_id,user_id,question_number,question,answer,topic,
               score,strengths,improvements,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, user_id, entry["question_number"], entry["question"],
                entry["transcript"], topic, float(evaluation.get("score", 0)),
                str(evaluation.get("strengths", "")), str(evaluation.get("improvements", "")),
                now_iso(),
            ),
        )
        return int(cursor.lastrowid)


def update_interview_summary(session_id: str, summary: str) -> None:
    with connection() as db:
        db.execute(
            "UPDATE interviews SET cumulative_summary=? WHERE session_id=?",
            (summary, session_id),
        )


def complete_interview(session_id: str, overall_score: float) -> None:
    with connection() as db:
        db.execute(
            """UPDATE interviews SET status='completed', overall_score=?, completed_at=?
               WHERE session_id=?""",
            (overall_score, now_iso(), session_id),
        )


def upsert_memory(
    user_id: str, kind: str, topic: str, content: str, source_answer_id: int,
) -> None:
    content = content.strip()
    if not content:
        return
    next_review = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    now = now_iso()
    with connection() as db:
        db.execute(
            """INSERT INTO memory_items(user_id,kind,topic,content,source_answer_id,
               first_seen,last_seen,next_review_at) VALUES(?,?,?,?,?,?,?,?)
               ON CONFLICT(user_id,kind,topic,content) DO UPDATE SET
               times_seen=memory_items.times_seen+1, last_seen=excluded.last_seen,
               confidence=MIN(0.95,memory_items.confidence+0.08), status='active',
               source_answer_id=excluded.source_answer_id""",
            (user_id, kind, topic, content, source_answer_id, now, now, next_review),
        )


def memory_context(user_id: str, topic: str = "", limit: int = 12) -> str:
    with connection() as db:
        rows = db.execute(
            """SELECT kind,topic,content,times_seen,confidence,next_review_at FROM memory_items
               WHERE user_id=? AND status='active' AND (?='' OR topic=? OR topic='')
               ORDER BY CASE WHEN next_review_at<=? THEN 0 ELSE 1 END,
                        times_seen DESC,last_seen DESC LIMIT ?""",
            (user_id, topic, topic, now_iso(), limit),
        ).fetchall()
    if not rows:
        return "No verified cross-interview memory yet."
    return "\n".join(
        f"- [{row['kind']}] {row['topic'] or 'general'}: {row['content']} "
        f"(seen {row['times_seen']}x, confidence {row['confidence']:.2f})"
        for row in rows
    )


def recent_questions(user_id: str, topic: str = "", limit: int = 20) -> list[str]:
    with connection() as db:
        rows = db.execute(
            """SELECT question FROM answers WHERE user_id=?
               AND relevance!='mismatch' AND (?='' OR topic=?)
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, topic, topic, limit),
        ).fetchall()
    return [row["question"] for row in rows]


def save_question_feedback(
    user_id: str, session_id: str, question_number: int, relevance: str, issue_type: str,
) -> None:
    with connection() as db:
        row = db.execute(
            """SELECT id FROM answers WHERE user_id=? AND session_id=? AND question_number=?""",
            (user_id, session_id, question_number),
        ).fetchone()
        if not row:
            raise ValueError("Answer not found")
        db.execute(
            "UPDATE answers SET relevance=?, issue_type=? WHERE id=?",
            (relevance, issue_type, row["id"]),
        )
        if relevance == "mismatch":
            db.execute(
                "UPDATE memory_items SET status='archived' WHERE source_answer_id=?",
                (row["id"],),
            )


def list_interviews(user_id: str, limit: int = 20) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT i.session_id,i.mode,i.topic,i.duration_minutes,i.overall_score,
               i.status,i.created_at,i.completed_at,i.cumulative_summary,
               COUNT(a.id) AS questions_answered
               FROM interviews i LEFT JOIN answers a ON a.session_id=i.session_id
               WHERE i.user_id=? GROUP BY i.session_id
               ORDER BY i.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_memory_items(user_id: str, limit: int = 50) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT m.id,m.kind,m.topic,m.content,m.confidence,m.times_seen,
               m.status,m.first_seen,m.last_seen,m.next_review_at,a.session_id,
               a.question,i.created_at AS interview_date,i.mode AS interview_mode
               FROM memory_items m
               LEFT JOIN answers a ON a.id=m.source_answer_id
               LEFT JOIN interviews i ON i.session_id=a.session_id
               WHERE m.user_id=? AND m.status='active'
               ORDER BY CASE WHEN m.next_review_at<=? THEN 0 ELSE 1 END,
                        m.times_seen DESC,m.last_seen DESC LIMIT ?""",
            (user_id, now_iso(), limit),
        ).fetchall()
    return [dict(row) for row in rows]


def create_user_topic(user_id: str, name: str, description: str) -> dict:
    name = " ".join(name.strip().split())
    description = " ".join(description.strip().split())
    if len(name) < 2 or len(name) > 60:
        raise ValueError("Topic name must contain 2 to 60 characters")
    if len(description) > 300:
        raise ValueError("Description must contain 300 characters or fewer")
    key = f"custom_{uuid.uuid4().hex[:12]}"
    try:
        with connection() as db:
            db.execute(
                "INSERT INTO user_topics(key,user_id,name,description,created_at) VALUES(?,?,?,?,?)",
                (key, user_id, name, description, now_iso()),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("A topic with this name already exists") from exc
    return {"key": key, "name": name, "description": description, "custom": True}


def list_user_topics(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT key,name,description FROM user_topics WHERE user_id=? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    return [{**dict(row), "custom": True} for row in rows]


def skill_statistics(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT COALESCE(NULLIF(topic,''),'general') AS topic,
               ROUND(AVG(score),1) AS score,COUNT(*) AS answers
               FROM answers WHERE user_id=? AND relevance!='mismatch'
               GROUP BY COALESCE(NULLIF(topic,''),'general')
               ORDER BY answers DESC,score DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_api_key(user_id: str, provider: str, api_key: str) -> None:
    provider = provider.strip().lower()
    encrypted = _cipher().encrypt(api_key.strip().encode())
    with connection() as db:
        db.execute(
            """INSERT INTO api_keys(user_id,provider,encrypted_key,last_four,updated_at)
               VALUES(?,?,?,?,?) ON CONFLICT(user_id,provider) DO UPDATE SET
               encrypted_key=excluded.encrypted_key,last_four=excluded.last_four,
               updated_at=excluded.updated_at""",
            (user_id, provider, encrypted, api_key.strip()[-4:], now_iso()),
        )


def api_key_for_user(user_id: str, provider: str = "groq") -> str | None:
    with connection() as db:
        row = db.execute(
            "SELECT encrypted_key FROM api_keys WHERE user_id=? AND provider=?",
            (user_id, provider),
        ).fetchone()
    if not row:
        return None
    try:
        return _cipher().decrypt(row["encrypted_key"]).decode()
    except InvalidToken:
        return None


def api_key_status(user_id: str, provider: str = "groq") -> dict:
    with connection() as db:
        row = db.execute(
            "SELECT last_four,updated_at FROM api_keys WHERE user_id=? AND provider=?",
            (user_id, provider),
        ).fetchone()
    return {
        "provider": provider,
        "configured": bool(row),
        "masked": f"••••••••{row['last_four']}" if row else "",
        "updated_at": row["updated_at"] if row else None,
    }


def delete_api_key(user_id: str, provider: str = "groq") -> bool:
    with connection() as db:
        result = db.execute(
            "DELETE FROM api_keys WHERE user_id=? AND provider=?", (user_id, provider)
        )
    return result.rowcount > 0
