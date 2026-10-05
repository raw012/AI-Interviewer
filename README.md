# AI Interview Coach

An English-first interview practice platform for adaptive mock interviews and focused technical training. The home screen puts interview practice first, while saved materials, past feedback, and API settings remain easy to find.

The application is built with React, FastAPI, and SQLite. Interview generation can use several model providers; audio transcription currently uses Groq or OpenAI.

## Features

### Practice home

- The primary action is starting an interview. Your last mode, topic, duration, and job description are reused for a one-click start when a source is available.
- Without working interview and transcription providers, the connection card becomes the main action and Start stays disabled. The card disappears when both providers are ready.
- A practice plant grows leaves outward as interviews are completed; the newest leaf unfurls on the feedback screen. Reduced-motion settings disable the animation.
- Desktop uses a compact sidebar; mobile uses a bottom tab bar for Home, Resume, Past interviews, and API settings.
- Profile and recording-review pages are hidden from the current navigation. Existing stored data and backend routes are preserved.

### Adaptive interviews

- General interviews based on a saved PDF resume and/or job description.
- 30-minute and 60-minute sessions with no fixed question count.
- The timer never interrupts an answer. When time expires, the current answer is evaluated before the interview ends.
- The prompt receives a compact session summary, the five most recent full Q&A pairs, relevant long-term memory, and recently asked questions to reduce repetition.
- Users can safely exit from interview setup, question preview, or an active interview.
- Camera and microphone permission is requested only when starting. The live transcript is hidden by default and can be revealed beneath the camera rather than over the video.

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
- Past interviews show each session's feedback summary and, when expanded, its questions, answers, scores, strengths, and improvement points.

### Resume and account persistence

- Email/password accounts with 30-day bearer sessions.
- One persistent PDF resume per account, replaceable at any time.
- SQLite persistence for accounts, interviews, answers, custom topics, memory, and settings.

### API key settings

- Save, replace, test, or remove personal provider API keys. Text generation supports the providers exposed in API settings; transcription currently supports Groq and OpenAI.
- Keys are encrypted before local database storage.
- The complete key is never returned to the browser after saving.
- A personal key takes precedence over a server fallback key where one is configured.

## Architecture

```text
React frontend (localhost:3000)
        |
        | Bearer-authenticated JSON / multipart requests
        v
FastAPI backend (localhost:8000)
        |
        +-- SQLite: users, resumes, interviews, answers, memory, settings
        +-- FFmpeg: video-to-audio extraction
        +-- Groq/OpenAI: transcription
        +-- Selected text provider: questions, scoring, and summaries
```

Runtime user data is written under `backend/data/`; uploaded recordings are written under `backend/uploads/`. Both directories are ignored by Git.

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- npm
- FFmpeg is provided by `imageio-ffmpeg` for video conversion
- A supported text-provider key and a Groq or OpenAI key for transcription (one Groq or OpenAI key can serve both roles)

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

## Hosted deployment

Build the frontend with `npm run build`, then start FastAPI from `backend/` with
`python -m uvicorn main:app --host 127.0.0.1 --port 8000`. When
`frontend/build/index.html` exists, FastAPI serves the frontend and API from
the same origin. Set `REACT_APP_API_URL` at build time only if the API uses a
different origin. A public deployment needs an HTTPS reverse proxy to the
FastAPI port and a process manager that keeps the backend running.

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
- The recording-review and profile interfaces are not part of this version's navigation; their existing stored data is not deleted.
