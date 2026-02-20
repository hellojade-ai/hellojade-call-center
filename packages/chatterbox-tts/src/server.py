"""Chatterbox TTS — OpenAI-compatible TTS API wrapper.

Exposes POST /v1/audio/speech so LiveKit's openai.TTS plugin
can talk to Chatterbox without a custom plugin.
"""

import io
import os
import torch
import torchaudio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Chatterbox TTS Server")

# Lazy-loaded model
_model = None
DEVICE = os.environ.get("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
VOICES_DIR = os.environ.get("VOICES_DIR", "/voices")


def get_model():
    global _model
    if _model is None:
        from chatterbox.tts import ChatterboxTTS
        _model = ChatterboxTTS.from_pretrained(device=DEVICE)
    return _model


class SpeechRequest(BaseModel):
    model: str = "chatterbox"
    input: str
    voice: str = "default"
    response_format: str = "wav"
    speed: float = 1.0


@app.post("/v1/audio/speech")
async def create_speech(request: SpeechRequest):
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text is empty")

    model = get_model()

    # Load voice embedding if specified and exists
    voice_path = os.path.join(VOICES_DIR, f"{request.voice}.pt")
    spk_emb = None
    if os.path.exists(voice_path):
        spk_emb = torch.load(voice_path, map_location=DEVICE)

    # Generate audio
    wav = model.generate(
        request.input,
        speaker_embedding=spk_emb,
    )

    # Encode to WAV
    buffer = io.BytesIO()
    torchaudio.save(buffer, wav.unsqueeze(0), sample_rate=24000, format="wav")
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "device": DEVICE}


@app.get("/v1/voices")
async def list_voices():
    """List available voice embeddings."""
    voices = []
    if os.path.isdir(VOICES_DIR):
        for f in os.listdir(VOICES_DIR):
            if f.endswith(".pt"):
                voices.append(f.removesuffix(".pt"))
    return {"voices": voices}
