# AI Interview Coach

An English-first interview practice platform that combines adaptive mock interviews, focused technical training, long-term candidate profiles, transparent memory, and real-interview recording review.

The application is built with React, FastAPI, SQLite, Groq Whisper, and Llama models.

## Features

### Candidate dashboard

- Six-dimensional candidate profile: Technical Depth, Communication, Structured Thinking, Problem Solving, Project Articulation, and Adaptability.
- Evidence explaining why each profile signal exists.
- Long-term strengths and growth areas linked to their source interview and question.
- Interview history with the compact context retained for each session.
- Optional, clearly labeled sample profile data for previewing a new account. Sample data can be removed at any time.

### Adaptive interviews

- General interviews based on a saved PDF resume and/or job description.
- 30-minute and 60-minute sessions with no fixed question count.
- The timer never interrupts an answer. When time expires, the current answer is evaluated before the interview ends.
- The prompt receives a compact session summary, the five most recent full Q&A pairs, relevant long-term memory, and recently asked questions to reduce repetition.
- Users can safely exit from interview setup, question preview, or an active interview.

### Specialized training

Built-in training domains include:

- Java OOP
- Computer Networks
- Operating Systems
- Machine Learning
- Data Structures & Algorithms
- Deep Learning

Users can also create account-specific custom training topics.

### Memory and feedback

- Interview answers produce reviewable strength and growth-area memories.
- Memories include confidence, recurrence, evidence question, and source interview.
- Post-interview feedback distinguishes a genuine knowledge gap from a mismatched question.
- Mismatched questions are excluded from future memory and repetition logic.

### Recording review

- Upload MP3, WAV, M4A, OGG, FLAC, WebM, MP4, MOV, or MKV files up to 200 MB.
- Automatically transcribe a real interview, infer Q&A boundaries, and produce question-level feedback.
- Recording reviews are stored separately and do **not** count as mock interviews or candidate-profile scores.

### Resume and account persistence

- Email/password accounts with 30-day bearer sessions.
- One persistent PDF resume per account, replaceable at any time.
- SQLite persistence for accounts, interviews, answers, custom topics, profile evidence, memory, and settings.

### API key settings

- Save, replace, test, or remove a personal Groq API key from the application.
- Keys are encrypted before local database storage.
- The complete key is never returned to the browser after saving.
- A personal key takes precedence over the server `GROQ_API_KEY` environment variable.

## Architecture

```text
React frontend (localhost:3000)
        |
        | Bearer-authenticated JSON / multipart requests
        v
FastAPI backend (localhost:8000)
        |
        +-- SQLite: users, resumes, interviews, answers, memory, profile, settings
        +-- FFmpeg: video-to-audio extraction
        +-- Groq Whisper: transcription
        +-- Llama: questions, scoring, summaries, and recording analysis
```

Runtime user data is written under `backend/data/`; uploaded recordings are written under `backend/uploads/`. Both directories are ignored by Git.

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- FFmpeg available on `PATH`
- A Groq API key for AI features

## Local setup

```bash
git clone https://github.com/raw012/AI-Interviewer.git
cd AI-Interviewer

python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements.txt

cd frontend
npm install
```

Create `backend/.env`:

```dotenv
GROQ_API_KEY=
```

The environment key is optional when users provide their own key through **API settings**.

### Start the backend

From the repository root:

```bash
cd backend
.venv/bin/python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Start the frontend

In another terminal:

```bash
cd frontend
npm start
```

Open [http://localhost:3000](http://localhost:3000).

## Verification

Build the frontend:

```bash
cd frontend
npm run build
```

Check backend imports:

```bash
PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m py_compile \
  backend/main.py backend/storage.py backend/evaluator.py backend/speech.py
```

## Privacy notes

- Do not commit `.env`, API keys, local databases, resumes, or recordings.
- The local encryption key used for saved provider credentials is stored under `backend/data/` with restricted file permissions.
- For a hosted deployment, use HTTPS, a managed secret store, production authentication, and a managed database.

## Current limitations

- Active interview sessions are held in backend memory, so restarting the backend ends an in-progress session.
- Profile scores become meaningful only after multiple relevant interviews. Sample data is a UI preview, not a real assessment.
- Speaker separation in uploaded recordings is inferred from the transcript and may require review when audio quality is poor.
