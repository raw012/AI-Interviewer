# AI Interview Coach

An English-first interview practice platform for adaptive mock interviews and focused technical training. The home screen puts interview practice first, while saved materials, past feedback, and API settings remain easy to find.

The application is built with React, FastAPI, and SQLite. Interview generation can use several model providers; audio transcription currently uses Groq or OpenAI.

## Features

### Practice home

- The primary action is starting an interview. Your last mode, topic, duration, and job description are reused for a one-click start when a source is available.
- Without working interview and transcription providers, a soft setup section offers direct links for each missing service and Start stays disabled. The section disappears when both providers are ready.
- Home focuses on starting an interview; completed interviews and feedback live in Past interviews rather than a duplicate recent-interviews panel.
- The flat blue-and-muted-green practice plant is part of the home background rather than a separate card. A small sprout appears from the start, and more leaves grow outward with completed interviews; the newest leaf unfurls on the feedback screen. Reduced-motion settings disable the animation.
- The signed-in app shows one Sign out control in the top-right account bar, including on the API settings page.
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

- First-time setup asks whether the user already has a key or needs one. The latter path links to Groq's API-key page; both paths test a key before saving it.
- Returning users see their current interview and transcription connections first, with options to change, test, or remove keys and reopen the guide.
- The top-left arrow leaves the current key-entry/help step first; from the API settings overview, it returns to the page that opened settings.
- Interview generation supports Groq, OpenAI, Anthropic, Google Gemini, and Qwen (China and International endpoints). The provider must match the service and region that issued the key. Transcription currently supports Groq and OpenAI, so other interview providers require a second key for spoken answers.
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

## Production hosting

Build the frontend, then serve the React application and FastAPI API from one
origin. FastAPI uses `frontend/build` by default; set `FRONTEND_BUILD_DIR` when
the build is stored elsewhere:

```bash
cd frontend && npm run build && cd ..
cd backend
FRONTEND_BUILD_DIR="$(pwd)/../frontend/build" \
  .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

In production, the frontend sends API requests to its own HTTPS origin. Put that
origin behind a TLS reverse proxy or a private-origin tunnel; do not expose the
Uvicorn development server directly to the internet.
Set `REACT_APP_API_URL` at build time only if the API uses a different origin.

## Verification and CI

Run the frontend checks before deployment:

```bash
cd frontend
CI=true npm test -- --watch=false --runInBand
npm run lint
npm run build
```

On the T7 drive, npm removes only verified macOS AppleDouble `._` sidecars before these commands. These files are metadata, not application code; otherwise Jest and ESLint may try to parse them as JavaScript.

Check the backend and run its unit tests:

```bash
PYTHONPATH=backend python3 -m unittest discover -s backend -p 'test_*.py'
python3 -m py_compile backend/main.py backend/storage.py backend/evaluator.py backend/providers.py backend/speech.py
```

The GitHub Actions workflow in `.github/workflows/ci.yml` repeats the frontend and backend checks on pushes and pull requests. A passing GitHub commit is not an automatic production deployment: the ieng6 server currently runs a separate checkout-free copy of the app and must be updated and health-checked separately. Restarts end any interview currently held in backend memory.

### Redeploy to ieng6

After the checks pass and `main` is pushed, run `bash scripts/deploy-ieng6.sh` from the repository root on a machine with access to `raw012@ieng6.ucsd.edu`. The script builds the committed release, uploads it over SSH, backs up the previous code and frontend build on the server, restarts only FastAPI, and checks both local and public health. It never replaces `backend/data` or `backend/videos`. The server's Cloudflare tunnel and existing five-minute process watchdog remain unchanged. A failed activation restores the previous code and build. This deployment step is deliberately manual; the repository does not contain a GitHub SSH private key or deployment secret.

## Privacy notes

- Do not commit `.env`, API keys, local databases, resumes, or recordings.
- The local encryption key used for saved provider credentials is stored under `backend/data/` with restricted file permissions.
- For a hosted deployment, use HTTPS, a managed secret store, production authentication, and a managed database.

## Current limitations

- Active interview sessions are held in backend memory, so restarting the backend ends an in-progress session.
- The recording-review and profile interfaces are not part of this version's navigation; their existing stored data is not deleted.
