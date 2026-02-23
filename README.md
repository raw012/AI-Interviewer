# AI Technical Interview Coach

AI-powered mock technical interview platform with real-time video recording, speech transcription, automated scoring, and adaptive follow-up question generation.

Built using React, FastAPI, Whisper (Groq API), and LLaMA-based evaluation.

---

## Overview

This project simulates a technical interview environment where users can:

- Record timed interview responses
- Transcribe speech to text automatically
- Receive AI-generated feedback and scores
- Get adaptive follow-up questions
- Review transcripts and performance summaries

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
