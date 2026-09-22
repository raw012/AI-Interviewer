import ffmpeg
import os
from pathlib import Path
from groq import Groq

def get_client(api_key: str | None = None) -> Groq:
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    return Groq(api_key=api_key)

def extract_audio(video_path: str) -> str:
    audio_path = str(Path(video_path).with_suffix(".wav"))

    (
        ffmpeg
        .input(video_path)
        .output(audio_path, format="wav")
        .run(overwrite_output=True)
    )

    return audio_path


def transcribe_audio(audio_path: str, api_key: str | None = None) -> str:
    with open(audio_path, "rb") as audio_file:
        transcript = get_client(api_key).audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file
        )

    return transcript.text
