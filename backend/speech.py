import ffmpeg
from pathlib import Path
from providers import transcribe_file

def extract_audio(video_path: str) -> str:
    audio_path = str(Path(video_path).with_suffix(".wav"))

    (
        ffmpeg
        .input(video_path)
        .output(audio_path, format="wav")
        .run(overwrite_output=True)
    )

    return audio_path


def transcribe_audio(audio_path: str, api_key: str, provider: str = "groq") -> str:
    return transcribe_file(provider, api_key, audio_path)
