# AI Technical Interview Coach

A full-stack mock interview platform that records your video responses, transcribes your speech, scores your answers with AI, and generates adaptive follow-up questions.

---

## What It Does

1. You paste a job description and the AI generates a relevant interview question
2. You record your answer on camera and microphone
3. Your speech is transcribed automatically
4. AI scores your answer (0–100) with detailed feedback
5. A follow-up or next question is generated based on your response
6. You can review your video playback, transcript, and a final performance summary

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, MediaRecorder API |
| Backend | FastAPI (Python) |
| Speech-to-Text | Groq Whisper API |
| AI Evaluation | LLaMA 3.1 (via Groq) |
| Audio Extraction | FFmpeg |

---

## Prerequisites

Before you begin, make sure you have the following installed:

- **Python** 3.8+
- **Node.js** 14+
- **FFmpeg** — [install guide below](#ffmpeg-installation)
- **Groq API Key** — get one free at [console.groq.com/keys](https://console.groq.com/keys)

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <project-folder>
```

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory:

```bash
# backend/.env
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

---

## Running the App

You need two terminals running simultaneously.

### Terminal 1 — Backend

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The backend runs at `http://localhost:8000`

### Terminal 2 — Frontend

```bash
cd frontend
npm start
```

The frontend runs at `http://localhost:3000` and opens automatically in your browser.

---

## Usage

1. Open `http://localhost:3000` in your browser
2. Paste a **job description** and click **Start Interview**
3. **Record your answer** — the timer counts down your response window
4. Wait for transcription and AI scoring to complete
5. Review your **score, feedback, and video playback**
6. Continue with follow-up or new questions
7. View your **final performance summary** at the end

---

## FFmpeg Installation

FFmpeg is required for audio extraction from your recorded video.

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get install ffmpeg

# Windows
choco install ffmpeg
```

---

## Troubleshooting

**Port already in use**

```bash
# Kill whatever is running on port 3000
lsof -i :3000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Or start the frontend on a different port
PORT=3001 npm start

# For the backend, use a different port
uvicorn main:app --port 8001
```

**API key not found**

Make sure `backend/.env` exists and contains your key:
```
GROQ_API_KEY=your_actual_key_here
```

**Virtual environment issues**

```bash
rm -rf backend/venv
python3 -m venv backend/venv
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

---

## License

Open source — free for educational and personal use.
