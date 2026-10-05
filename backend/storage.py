"""Local SQLite persistence for accounts, resumes, interview history, and memory."""

from __future__ import annotations

import hashlib
import json
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


# Use UTC consistently for persisted timestamps.
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Open a SQLite connection with named rows and foreign keys enabled.
def connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


# Load or create the local key used to encrypt provider credentials.
def _cipher() -> Fernet:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.write_bytes(Fernet.generate_key())
        SECRET_KEY_PATH.chmod(0o600)
    return Fernet(SECRET_KEY_PATH.read_bytes().strip())


# Create the account, interview, memory, and settings tables if absent.
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

            CREATE TABLE IF NOT EXISTS profile_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                dimension TEXT NOT NULL,
                score REAL NOT NULL,
                evidence TEXT NOT NULL,
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_provider_settings (
                user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                llm_provider TEXT NOT NULL DEFAULT 'groq',
                transcription_provider TEXT NOT NULL DEFAULT 'groq',
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_answers_user_topic
                ON answers(user_id, topic, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_user_status
                ON memory_items(user_id, status, next_review_at);
            """
        )
        answer_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(answers)").fetchall()
        }
        if "dimension_scores" not in answer_columns:
            db.execute(
                "ALTER TABLE answers ADD COLUMN dimension_scores TEXT NOT NULL DEFAULT '{}'"
            )
        memory_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(memory_items)").fetchall()
        }
        if "is_demo" not in memory_columns:
            db.execute(
                "ALTER TABLE memory_items ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0"
            )


# Derive a salted password hash for storage and comparison.
def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"{PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


# Compare a password with its stored hash.
def _password_valid(password: str, encoded: str) -> bool:
    try:
        iterations, salt, expected = encoded.split("$", 2)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), int(iterations)
        )
        return secrets.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


# Return only safe account fields to API callers.
def _public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "name": row["name"]}


# Insert a new account after validating its credentials.
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


# Find an account only when its password matches.
def authenticate_user(email: str, password: str) -> dict | None:
    with connection() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email=?", (email.strip().lower(),)
        ).fetchone()
    return _public_user(row) if row and _password_valid(password, row["password_hash"]) else None


# Create a time-limited bearer token for an account.
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


# Resolve an unexpired bearer token to its account.
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


# Replace the account's saved PDF and extracted text.
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


# Read resume metadata, optionally including PDF bytes.
def resume_for_user(user_id: str, include_pdf: bool = False) -> dict | None:
    columns = "filename,extracted_text,updated_at" + (",pdf" if include_pdf else "")
    with connection() as db:
        row = db.execute(f"SELECT {columns} FROM resumes WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


# Remove the account's saved resume if present.
def delete_resume(user_id: str) -> bool:
    with connection() as db:
        result = db.execute("DELETE FROM resumes WHERE user_id=?", (user_id,))
    return result.rowcount > 0


# Persist a newly started interview session.
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


# Persist an evaluated answer and return its question number.
def save_answer(user_id: str, session_id: str, entry: dict, topic: str) -> int:
    evaluation = entry["evaluation"]
    with connection() as db:
        cursor = db.execute(
            """INSERT INTO answers(session_id,user_id,question_number,question,answer,topic,
               score,strengths,improvements,dimension_scores,created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, user_id, entry["question_number"], entry["question"],
                entry["transcript"], topic, float(evaluation.get("score", 0)),
                str(evaluation.get("strengths", "")), str(evaluation.get("improvements", "")),
                json.dumps(evaluation.get("dimension_scores", {})),
                now_iso(),
            ),
        )
        return int(cursor.lastrowid)


# Replace the compact running summary for one interview.
def update_interview_summary(session_id: str, summary: str) -> None:
    with connection() as db:
        db.execute(
            "UPDATE interviews SET cumulative_summary=? WHERE session_id=?",
            (summary, session_id),
        )


# Mark a session complete with its final score.
def complete_interview(session_id: str, overall_score: float) -> None:
    with connection() as db:
        db.execute(
            """UPDATE interviews SET status='completed', overall_score=?, completed_at=?
               WHERE session_id=?""",
            (overall_score, now_iso(), session_id),
        )


# Mark an abandoned interview as cancelled.
def cancel_interview(session_id: str) -> None:
    with connection() as db:
        db.execute(
            """UPDATE interviews SET status='cancelled', completed_at=?
               WHERE session_id=? AND status='active'""",
            (now_iso(), session_id),
        )


# Merge a new strength, gap, or user insight into long-term memory.
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


# Format relevant long-term memory for the next model prompt.
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


# Return prior questions to help the model avoid repetition.
def recent_questions(user_id: str, topic: str = "", limit: int = 20) -> list[str]:
    with connection() as db:
        rows = db.execute(
            """SELECT question FROM answers WHERE user_id=?
               AND relevance!='mismatch' AND (?='' OR topic=?)
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, topic, topic, limit),
        ).fetchall()
    return [row["question"] for row in rows]


# Store whether the user felt a question matched the interview.
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


# List sessions and their feedback summaries for history views.
def list_interviews(user_id: str, limit: int | None = 20) -> list[dict]:
    with connection() as db:
        limit_clause = " LIMIT ?" if limit is not None else ""
        rows = db.execute(
            """SELECT i.session_id,i.mode,i.topic,i.duration_minutes,i.overall_score,
               i.status,i.created_at,i.completed_at,i.cumulative_summary,
               COUNT(a.id) AS questions_answered
               FROM interviews i LEFT JOIN answers a ON a.session_id=i.session_id
               WHERE i.user_id=? AND i.mode!='recording' AND i.status!='cancelled'
               GROUP BY i.session_id
               ORDER BY i.created_at DESC""" + limit_clause,
            (user_id, limit) if limit is not None else (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# Count completed sessions for the practice plant.
def completed_interview_count(user_id: str) -> int:
    with connection() as db:
        row = db.execute(
            "SELECT COUNT(*) AS total FROM interviews WHERE user_id=? AND mode!='recording' AND status='completed'",
            (user_id,),
        ).fetchone()
    return int(row["total"])


# Return all answers in an owned interview.
def interview_answers(user_id: str, session_id: str) -> list[dict] | None:
    with connection() as db:
        interview = db.execute(
            "SELECT session_id FROM interviews WHERE session_id=? AND user_id=? AND mode!='recording'",
            (session_id, user_id),
        ).fetchone()
        if not interview:
            return None
        rows = db.execute(
            """SELECT question_number,question,answer,score,strengths,improvements,
               relevance,issue_type FROM answers WHERE session_id=? AND user_id=?
               ORDER BY question_number""",
            (session_id, user_id),
        ).fetchall()
    return [dict(row) for row in rows]


# Return saved retrospective reviews of uploaded recordings.
def list_recording_reviews(user_id: str, limit: int = 20) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT i.session_id,i.mode,i.topic,i.duration_minutes,i.overall_score,
               i.status,i.created_at,i.completed_at,i.cumulative_summary,
               COUNT(a.id) AS questions_answered
               FROM interviews i LEFT JOIN answers a ON a.session_id=i.session_id
               WHERE i.user_id=? AND i.mode='recording' AND i.status!='cancelled'
               GROUP BY i.session_id ORDER BY i.created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


# Return the user's current long-term memory items.
def list_memory_items(user_id: str, limit: int = 50) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT m.id,m.kind,m.topic,m.content,m.confidence,m.times_seen,m.is_demo,
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


# Save a custom specialized-training topic.
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


# List custom topics available to one account.
def list_user_topics(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT key,name,description FROM user_topics WHERE user_id=? ORDER BY created_at",
            (user_id,),
        ).fetchall()
    return [{**dict(row), "custom": True} for row in rows]


# Aggregate topic-level scores from past answers.
def skill_statistics(user_id: str) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            """SELECT COALESCE(NULLIF(a.topic,''),'general') AS topic,
               ROUND(AVG(a.score),1) AS score,COUNT(*) AS answers
               FROM answers a JOIN interviews i ON i.session_id=a.session_id
               WHERE a.user_id=? AND a.relevance!='mismatch'
               AND i.mode!='recording' AND i.status!='cancelled'
               GROUP BY COALESCE(NULLIF(a.topic,''),'general')
               ORDER BY answers DESC,score DESC""",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


PROFILE_DIMENSIONS = {
    "technical_depth": "Technical Depth",
    "communication": "Communication",
    "structured_thinking": "Structured Thinking",
    "problem_solving": "Problem Solving",
    "project_articulation": "Project Articulation",
    "adaptability": "Adaptability",
}


# Aggregate behavioral and technical profile dimensions.
def profile_dimension_statistics(user_id: str) -> dict:
    values: dict[str, list[float]] = {key: [] for key in PROFILE_DIMENSIONS}
    with connection() as db:
        answer_rows = db.execute(
            """SELECT a.dimension_scores,a.question,a.created_at,i.session_id
               FROM answers a JOIN interviews i ON i.session_id=a.session_id
               WHERE a.user_id=? AND a.relevance!='mismatch'
               AND i.mode!='recording' AND i.status!='cancelled'
               ORDER BY a.created_at DESC LIMIT 30""",
            (user_id,),
        ).fetchall()
        sample_rows = db.execute(
            """SELECT dimension,score,evidence,is_demo,created_at FROM profile_samples
               WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()

    for row in answer_rows:
        try:
            scores = json.loads(row["dimension_scores"] or "{}")
        except json.JSONDecodeError:
            scores = {}
        for key, score in scores.items():
            if key in values and isinstance(score, (int, float)):
                values[key].append(float(score))
    for row in sample_rows:
        if row["dimension"] in values:
            values[row["dimension"]].append(float(row["score"]))

    dimensions = [
        {
            "key": key,
            "name": name,
            "score": round(sum(values[key]) / len(values[key]), 1) if values[key] else None,
            "samples": len(values[key]),
        }
        for key, name in PROFILE_DIMENSIONS.items()
    ]
    return {
        "dimensions": dimensions,
        "has_demo_data": any(bool(row["is_demo"]) for row in sample_rows),
    }


# Add sample profile data for an account without interviews.
def seed_demo_profile(user_id: str) -> int:
    demo = [
        ("technical_depth", 74, "Explains core concepts accurately and identifies meaningful engineering trade-offs."),
        ("communication", 68, "Communicates the main idea clearly, but examples could be more concise and specific."),
        ("structured_thinking", 81, "Breaks broad questions into assumptions, approach, trade-offs, and conclusion."),
        ("problem_solving", 76, "Uses constraints and failure modes to narrow down practical solutions."),
        ("project_articulation", 63, "Describes responsibilities well; impact and personal contribution need stronger evidence."),
        ("adaptability", 72, "Responds constructively to follow-up questions and adjusts the answer when challenged."),
    ]
    with connection() as db:
        existing = db.execute(
            "SELECT COUNT(*) AS count FROM profile_samples WHERE user_id=? AND is_demo=1",
            (user_id,),
        ).fetchone()["count"]
        if not existing:
            db.executemany(
                """INSERT INTO profile_samples(user_id,dimension,score,evidence,is_demo,created_at)
                   VALUES(?,?,?,?,1,?)""",
                [(user_id, dimension, score, evidence, now_iso()) for dimension, score, evidence in demo],
            )
        demo_memories = [
            ("expertise", "system_design", "Shows growing expertise in breaking down ambiguous system-design problems."),
            ("communication_pattern", "general", "Usually communicates the main idea clearly, then benefits from adding one concrete example."),
            ("working_style", "general", "Approaches problems by identifying constraints and failure modes before choosing a solution."),
            ("preference", "general", "Appears most comfortable with structured technical discussions and follow-up questions."),
        ]
        now = now_iso()
        db.executemany(
            """INSERT OR IGNORE INTO memory_items(
               user_id,kind,topic,content,confidence,times_seen,status,
               source_answer_id,first_seen,last_seen,next_review_at,is_demo)
               VALUES(?,?,?,?,0.55,1,'active',NULL,?,?,NULL,1)""",
            [(user_id, kind, topic, content, now, now) for kind, topic, content in demo_memories],
        )
    return 0 if existing else len(demo)


# Remove only the account's sample profile data.
def delete_demo_profile(user_id: str) -> int:
    with connection() as db:
        result = db.execute(
            "DELETE FROM profile_samples WHERE user_id=? AND is_demo=1", (user_id,)
        )
        db.execute("DELETE FROM memory_items WHERE user_id=? AND is_demo=1", (user_id,))
    return result.rowcount


# Encrypt and save a personal provider API key.
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


# Decrypt a key for server-side model calls only.
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


# Return masked key metadata without disclosing the secret.
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


# Read the active text and transcription provider choices.
def provider_settings(user_id: str) -> dict:
    with connection() as db:
        row = db.execute(
            "SELECT llm_provider,transcription_provider FROM user_provider_settings WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {"llm_provider": "groq", "transcription_provider": "groq"}


# Save active providers for future interviews.
def save_provider_settings(
    user_id: str, llm_provider: str, transcription_provider: str
) -> dict:
    with connection() as db:
        db.execute(
            """INSERT INTO user_provider_settings(
               user_id,llm_provider,transcription_provider,updated_at) VALUES(?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
               llm_provider=excluded.llm_provider,
               transcription_provider=excluded.transcription_provider,
               updated_at=excluded.updated_at""",
            (user_id, llm_provider, transcription_provider, now_iso()),
        )
    return provider_settings(user_id)


# Delete a saved provider key without touching other keys.
def delete_api_key(user_id: str, provider: str = "groq") -> bool:
    with connection() as db:
        result = db.execute(
            "DELETE FROM api_keys WHERE user_id=? AND provider=?", (user_id, provider)
        )
    return result.rowcount > 0
