import ffmpeg
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    raise ValueError("GROQ_API_KEY environment variable is not set")

client = Groq(api_key=api_key)

def extract_audio(video_path: str) -> str:
    audio_path = video_path.replace(".webm", ".wav")

    (
        ffmpeg
        .input(video_path)
        .output(audio_path, format="wav")
        .run(overwrite_output=True)
    )

    return audio_path


def transcribe_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file
        )

    return transcript.text