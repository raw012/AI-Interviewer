from dotenv import load_dotenv
load_dotenv()
from evaluator import generate_followup, score_answer
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os

from speech import extract_audio, transcribe_audio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

@app.post("/start")
def start_interview():
    session_id = str(uuid.uuid4())

    sessions[session_id] = {
        "stage": 0,
        "history": []
    }

    return {
        "session_id": session_id,
        "question": "Tell me about yourself."
    }


@app.post("/upload/{session_id}")
async def upload_answer(session_id: str, file: UploadFile = File(...)):

    os.makedirs("videos", exist_ok=True)

    video_path = f"videos/{uuid.uuid4()}.webm"

    with open(video_path, "wb") as f:
        f.write(await file.read())
    # 提取音频
    audio_path = extract_audio(video_path)
    # 转文字
    transcript = transcribe_audio(audio_path)

    # 打分
    evaluation = score_answer(transcript)

    # 生成 follow-up
    followup = generate_followup(transcript)

    print("Transcript:", transcript)
    print("Evaluation:", evaluation)
    print("Next Question:", followup)

    return {
        "transcript": transcript,
        "evaluation": evaluation,
        "next_question": followup
    }