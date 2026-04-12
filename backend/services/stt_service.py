"""Speech-to-Text service using Groq Whisper."""

import os
import tempfile
from fastapi import HTTPException, status
from groq import Groq


GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


async def transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """
    Transcribe audio using Groq Whisper (whisper-large-v3).
    
    Args:
        audio_bytes: Audio file content (bytes)
        filename: Original filename for reference
    
    Returns:
        Transcript string
    
    Raises:
        HTTPException 503 on transcription failure
    """
    if not GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech transcription service not configured",
        )

    # Save audio to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name

    try:
        # Transcribe using Groq Whisper
        with open(temp_path, "rb") as f:
            transcript = groq_client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
            )
        return transcript.text
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Speech transcription failed: {str(e)}. Please try again.",
        )
    finally:
        # Clean up temp file
        try:
            os.remove(temp_path)
        except Exception:
            pass
