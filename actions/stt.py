"""
Speech-to-Text powered by Gemini (audio transcription).
Simple pipeline: buffer audio with VAD → send to Gemini → return text.
"""

import io
import wave
from google import genai
from google.genai import types


class GeminiTranscriber:
    """Transcribe speech segments via Gemini's audio understanding."""

    def __init__(self, api_key: str):
        self._client = genai.Client(api_key=api_key)

    def transcribe(self, audio_bytes: bytes, lang: str = "de") -> str:
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio_bytes)

        resp = self._client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=[
                f"Transcribe the {lang} speech in this audio. Only return the transcribed text.",
                types.Part.from_bytes(data=wav_buf.getvalue(), mime_type="audio/wav"),
            ],
        )
        return resp.text.strip()


class FrameBuffer:
    """Accumulates audio chunks and yields fixed-size VAD frames (30ms @ 16kHz)."""

    def __init__(self, frame_ms: int = 30, sample_rate: int = 16000):
        self.frame_bytes = int(sample_rate * frame_ms / 1000) * 2
        self.buf = bytearray()

    def add(self, chunk: bytes):
        self.buf.extend(chunk)

    def pop_frames(self):
        n = self.frame_bytes
        while len(self.buf) >= n:
            yield bytes(self.buf[:n])
            self.buf = self.buf[n:]


def rms_vad(frame: bytes, threshold: float = 350.0) -> bool:
    """Simple RMS-based voice activity detection."""
    import numpy as np
    audio = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(audio ** 2))) > threshold
