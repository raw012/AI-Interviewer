# AI Technical Interview Coach

AI-powered, time-based mock technical interview platform with real-time video recording, speech transcription, automated scoring, and context-aware question generation.

Built using React, FastAPI, Whisper (Groq API), and LLaMA-based evaluation.

---

## Overview

This project simulates a technical interview environment where users can:

- Choose a 30-minute or 60-minute interview
- Record timed interview responses without a fixed question limit
- Transcribe speech to text automatically
- Receive AI-generated feedback and scores
- Get adaptive questions using a compact interview summary plus the five most recent full Q&A pairs
- Review transcripts and performance summaries

When the interview timer expires, the current answer is not interrupted. The interview ends after that answer is submitted and evaluated, then displays a feedback table containing each question, answer, improvement advice, and score.

The system integrates browser media capture, backend audio processing, and large language model evaluation into a complete full-stack workflow.

---

## Tech Stack

### Frontend
- React (JavaScript)
- MediaRecorder API
- Fetch API

### Backend
- FastAPI (Python)
- FFmpeg (audio extraction)
- Groq Whisper API (speech-to-text)
- LLaMA 3 (evaluation and follow-up generation)
- UUID-based session management

---

## Project Structure
AI-Interview-Coach/

│
├── frontend/

│ ├── src/

│ └── package.json

│

├── backend/

│ ├── main.py

│ ├── evaluator.py

│ ├── speech.py

│ ├── requirements.txt

│ └── videos/

│

└── README.md

## Installation
### Clone Repository
### Add YOUR OWN Grok API Key
