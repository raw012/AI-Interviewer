# AI Technical Interview Coach

A full-stack AI mock interview platform supporting four modes: **Coding**, **Resume-based**, **Technical**, and **Behavioral**. Users speak or type their answers, receive AI-generated scores and feedback, and get adaptive follow-up questions that probe 2–3 layers deep. Session history is stored per user with a free tier of 10 AI requests per day.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Monaco Editor |
| Backend | FastAPI (Python) |
| Database | PostgreSQL + Redis |
| Auth | JWT |
| LLM | Gemini 1.5 Flash → Groq LLaMA 3.1 (fallback) |
| Speech-to-Text | Groq Whisper (`whisper-large-v3`) |

---

## Installation & Setup

**Prerequisites:** Python 3.8+, Node.js 14+, PostgreSQL, Redis

### Backend
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```bash
GEMINI_API_KEY=        # https://aistudio.google.com/apikey
GROQ_API_KEY=          # https://console.groq.com/keys
POSTGRES_URL=postgresql+asyncpg://user:password@localhost:5432/interview_db
REDIS_URL=redis://localhost:6379
JWT_SECRET=            # python3 -c "import secrets; print(secrets.token_hex(32))"
STRIPE_PUBLISHABLE_KEY=placeholder
```

```bash
alembic upgrade head   # initialize database tables
```

### Frontend
```bash
cd frontend && npm install
```

---

## Running

```bash
# Terminal 1 — backend (http://localhost:8000)
cd backend && source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — frontend (http://localhost:3000)
cd frontend && npm start
```
