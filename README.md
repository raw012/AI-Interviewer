# AI Interviewer

Mock interviews with an interviewer that listens, follows up on what you said, runs your code, and coaches you afterwards.

Live: https://interview.buildbyray.dev

## What it does

1. **Say what you're preparing for.** One text box (or dictate): "Google SWE intern, interviews in three weeks." The app asks only for what's missing: role, internship or full-time, level, company.
2. **Check the interview brief.** A short description of the real loop for that company, role and level, with sources. Pick the rounds, length, interviewer and style.
3. **Do the interview.** The interviewer speaks, you answer by voice or typing. Follow-ups depend on your answer. Coding rounds open a workspace where you write, run and test code.
4. **Get coached.** A report scores each answer against a rubric, shows what worked and what was missing, asks guiding questions before revealing a stronger approach, and lets you re-answer to see the difference. You can hear the debrief read aloud.
5. **Come back.** The app remembers the skills worth revisiting and brings them back on a spaced schedule.

## How it works

| Area | Approach |
|---|---|
| Questions | About 190 questions tagged by role, level, company and competency, each with a rubric and follow-ups. Every question is labelled *official guidance*, *commonly reported* or *practice*; the app never claims a company asked something without a source. |
| Recent coding questions | `question_refresh.py` pulls public candidate-reported "last 30 days" lists per company each week and re-ranks the 28 runnable coding problems for the target company. |
| Code workspace | Python (Pyodide) and JavaScript run in the browser in a Web Worker with a time limit. Nothing executes on the server. Test results go to the interviewer. |
| Tokens | One model call per turn scores the answer, updates a 600-character running summary, proposes memory and writes the next line. The system prompt is fixed per session so providers can cache it. Usage is logged per interview. |
| Evaluation | Explicit rubric per question, a 1–5 scale anchored to the target level, quoted evidence, per-competency scores, temperature 0. The overall score is computed, not asked for. |
| Memory | Stores growth areas, strengths, stories told, background and preferences. Never stores recordings or sensitive personal data. One-off slips expire; growth areas are reviewed at 1, 3, 7, 14 and 30 days. Users can view, edit and delete everything. |
| Voice | Four interviewers with their own voices (Groq Orpheus, ElevenLabs optional, device voice as fallback). Speech-to-text with Whisper. |
| Accounts | Email and password or Google sign-in, data export, sign out other devices, account deletion. |

## Stack

React 19 (Create React App) · FastAPI · SQLite · Groq / OpenAI / Anthropic / Gemini / Qwen for the model · Groq or OpenAI Whisper for transcription.

```
backend/
  studio.py            API routes
  intake.py            goal parsing, clarifying questions, role brief
  engine.py            planning, turns, adaptive difficulty, coaching report
  memory.py            memory policy and spaced review
  knowledge.py         roles, levels, rounds, company formats, personas
  question_seed.py     question bank        coding_problems.py  runnable problems
  question_refresh.py  weekly trending refresh
frontend/src/studio/   Home, Intake, Room, CodeWorkspace, Report, Memory, Settings
```

## Run locally

```bash
python3 -m venv backend/.venv && backend/.venv/bin/pip install -r requirements.txt
cp backend/.env.example backend/.env        # optional server-side keys
cd backend && .venv/bin/python -m uvicorn main:app --reload --port 8000
```

```bash
cd frontend && npm ci && npm start          # http://localhost:3000
```

Each user can connect their own provider key in Settings (Groq has a free tier). Keys are encrypted at rest.

Optional environment variables: `GROQ_API_KEY`, `ELEVENLABS_API_KEY`, `GOOGLE_CLIENT_ID` (enables the Google button), `TAVILY_API_KEY` or `BRAVE_API_KEY` (live web search in briefs).

## Test and deploy

```bash
STUDIO_NO_REFRESH=1 PYTHONPATH=backend python -m unittest discover -s backend -p 'test_*.py'
cd frontend && npm run lint && CI=true npm test -- --watchAll=false && npm run build
```

`bash scripts/deploy-ieng6.sh` builds the pushed commit, uploads it, backs up code and database, restarts the API and rolls back on failure. Use `DEPLOY_BRANCH=<branch>` to preview a branch. Refresh trending questions weekly with `python backend/question_refresh.py` (the API also refreshes on startup when data is over a week old).

## Licence

Copyright © 2026 Yirui (Ray) Wang. Source is available under the [PolyForm Noncommercial License 1.0.0](LICENSE): you may read, run and modify it for noncommercial purposes. Commercial use is reserved to the copyright holder.
