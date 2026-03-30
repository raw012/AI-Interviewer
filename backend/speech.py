import ffmpeg
import os
from groq import Groq

client = Groq(api_key="#filled with the key")

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