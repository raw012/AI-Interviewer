"""Self-hosted interviewer voice: Kokoro-82M (Apache-2.0) run through ONNX on the CPU.

No API key and no per-request cost. A voice spec names one Kokoro voice or a weighted
blend, with an optional speed, e.g. "af_sarah" or "af_kore*0.7+zf_xiaoxiao*0.3@0.95".
The model is loaded once, lazily, and synthesis is serialised so a shared server stays
responsive."""

from __future__ import annotations

import io
import os
import threading
import wave
from pathlib import Path

MODEL_DIR = Path(os.getenv("KOKORO_DIR") or Path(__file__).resolve().parent / "models" / "kokoro")
MODEL_FILE = MODEL_DIR / "kokoro-v1.0.onnx"
VOICES_FILE = MODEL_DIR / "voices-v1.0.bin"
THREADS = max(1, int(os.getenv("KOKORO_THREADS", "4")))

_lock = threading.Lock()
_engine = None


def available() -> bool:
    """True when the model files and runtime are installed; does not load the model."""
    if os.getenv("KOKORO_DISABLED") or not (MODEL_FILE.exists() and VOICES_FILE.exists()):
        return False
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    return True


def parse_spec(spec: str) -> tuple[list[tuple[str, float]], float]:
    """Split 'a*0.7+b*0.3@0.95' into ([('a', 0.7), ('b', 0.3)], 0.95)."""
    body, _, speed_text = spec.strip().partition("@")
    parts: list[tuple[str, float]] = []
    for item in body.split("+"):
        name, _, weight = item.strip().partition("*")
        if not name:
            raise ValueError(f"Empty voice in spec {spec!r}")
        parts.append((name, float(weight) if weight else 1.0))
    total = sum(w for _, w in parts)
    if total <= 0:
        raise ValueError(f"Voice weights must be positive in {spec!r}")
    speed = float(speed_text) if speed_text else 1.0
    if not 0.5 <= speed <= 2.0:
        raise ValueError("Speed must be between 0.5 and 2.0")
    return [(n, w / total) for n, w in parts], speed


def _load():
    global _engine
    if _engine is None:
        import onnxruntime as ort
        from kokoro_onnx import Kokoro

        ort.set_default_logger_severity(3)
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(MODEL_FILE), options, providers=["CPUExecutionProvider"])
        _engine = Kokoro.from_session(session, str(VOICES_FILE))
    return _engine


def _to_wav(samples, rate: int) -> bytes:
    import numpy as np

    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(pcm)
    return out.getvalue()


def synthesize(text: str, spec: str) -> bytes:
    """Speak English text in the given voice spec and return 16-bit mono WAV bytes."""
    parts, speed = parse_spec(spec)
    with _lock:
        engine = _load()
        known = set(engine.get_voices())
        unknown = [n for n, _ in parts if n not in known]
        if unknown:
            raise ValueError(f"Unknown Kokoro voice: {', '.join(unknown)}")
        style = sum(w * engine.get_voice_style(n) for n, w in parts)
        # British voices read best with British pronunciation; everything else is US English.
        lang = "en-gb" if parts[0][0][:1] == "b" else "en-us"
        samples, rate = engine.create(text, voice=style, speed=speed, lang=lang)
    return _to_wav(samples, rate)
