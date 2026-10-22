"""Optional multilingual Listen Back fallback.

Uses installed browser voices first (frontend), then the public edge-tts service
when it advertises a matching locale. External service, not for confidential
production complaints without informed consent and provider review.
"""
import asyncio
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/voice", tags=["Voice accessibility"])

# Exact locales are required: never speak Odia using another language's voice.
_LOCALES = {
    "en": "en-IN", "hi": "hi-IN", "te": "te-IN", "or": "or-IN",
    "bn": "bn-IN", "ta": "ta-IN", "kn": "kn-IN", "ml": "ml-IN",
    "mr": "mr-IN", "gu": "gu-IN", "pa": "pa-IN", "ur": "ur-IN",
    "as": "as-IN", "ne": "ne-NP", "brx": "brx-IN", "doi": "doi-IN",
    "ks": "ks-IN", "kok": "kok-IN", "mai": "mai-IN", "mni": "mni-IN",
    "sa": "sa-IN", "sat": "sat-IN", "sd": "sd-IN",
}

class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1800)
    lang: str = Field(default="or-IN", min_length=2, max_length=24)

_voice_cache = {}
_cache_updated = 0.0
_cache_lock = asyncio.Lock()


def _normalize_locale(value):
    value = value.strip().replace("_", "-")
    return _LOCALES.get(value.lower(), value)

async def _get_voices():
    global _voice_cache, _cache_updated
    if _voice_cache and time.monotonic() - _cache_updated < 3600:
        return _voice_cache
    async with _cache_lock:
        if _voice_cache and time.monotonic() - _cache_updated < 3600:
            return _voice_cache
        try:
            import edge_tts
        except ImportError:
            raise HTTPException(503, "Voice fallback needs edge-tts: pip install -r requirements.txt")
        try:
            results = await asyncio.wait_for(edge_tts.list_voices(), timeout=12)
        except Exception:
            raise HTTPException(503, "Online voice catalog is unavailable. Check your internet connection.")
        _voice_cache = {v["Locale"].lower(): v["ShortName"] for v in results if v.get("Locale") and v.get("ShortName")}
        _cache_updated = time.monotonic()
        return _voice_cache


@router.get("/languages")
async def available_online_voices():
    voices = await _get_voices()
    return {"locales": sorted(voices.keys()), "note": "Online voices only; browser voice availability varies by device."}


@router.post("/speak")
async def synthesize_speech(data: SpeechRequest):
    locale = _normalize_locale(data.lang).lower()
    # Refuse arbitrary or malformed locales to avoid misuse of speech proxy.
    if not locale.replace("-", "").isalpha() or len(locale) > 16:
        raise HTTPException(422, "Invalid language locale")
    voices = await _get_voices()
    voice = voices.get(locale)
    if not voice:
        raise HTTPException(422, f"No online Listen Back voice is available for {data.lang}.")
    import edge_tts
    chunks = []
    async def render():
        async for chunk in edge_tts.Communicate(data.text, voice).stream():
            if chunk.get("type") == "audio":
                chunks.append(chunk["data"])
    try:
        await asyncio.wait_for(render(), timeout=22)
    except Exception:
        raise HTTPException(503, "Online speech generation failed. Try again later.")
    audio = b"".join(chunks)
    if not audio:
        raise HTTPException(503, "The speech provider returned no audio.")
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.post("/odia")
async def legacy_odia_speech(data: SpeechRequest):
    # Preserve compatibility with earlier frontend releases.
    return await synthesize_speech(SpeechRequest(text=data.text, lang="or-IN"))
