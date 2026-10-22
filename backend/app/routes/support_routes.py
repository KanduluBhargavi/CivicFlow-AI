import os
import traceback
import logging
import time
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # The optional support chat must not prevent core API startup.
    genai = None
    genai_types = None


# Load environment variables
load_dotenv()


router = APIRouter(
    prefix="/support",
    tags=["AI Support"]
)


# ================= REQUEST MODEL =================

class ChatRequest(BaseModel):
    message: str


# ================= GEMINI CONFIGURATION =================

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
logger = logging.getLogger(__name__)
client = None


def _get_gemini_client():
    global client
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI support chat is not configured. Core CivicFlow features remain available.",
        )
    if genai is None or genai_types is None:
        raise HTTPException(status_code=503, detail="AI support chat dependencies are unavailable.")
    if client is None:
        client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=genai_types.HttpOptions(timeout=8000),
        )
    return client


# ================= AI SUPPORT CHAT =================

@router.post("/chat")
def chat_with_support(request: ChatRequest):
    question = request.message.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Please type a question.")
    if len(question) > 1500:
        raise HTTPException(status_code=422, detail="Question is too long (maximum 1500 characters).")
    gemini_client = _get_gemini_client()

    prompt = f"""You are CivicFlow AI Support Assistant for a public grievance platform in India.
Guide users clearly on filing and tracking grievances, department routing, status updates,
multilingual text entry, incidents and resolution reviews. Explain accurately that you cannot
view a personal complaint or change case status without the relevant app workflow.
Do not make up complaint records, support contacts, SLA deadlines, or supported languages.
Use simple, concise language, usually 2-4 sentences. Answer the actual question first.
User question: {question}"""

    for attempt in range(2):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_CHAT_MODEL,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=220,
                ),
            )
            reply = (response.text or "").strip()
            if reply:
                return {"reply": reply}
            raise HTTPException(status_code=502, detail="Empty AI response")
        except HTTPException:
            raise
        except Exception as exc:
            # Provider SDK raises exceptions with status codes. Temporary outages are retriable.
            status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            details = str(exc).lower()
            transient = (str(status) in ("429", "500", "502", "503", "504") or
                         any(x in details for x in ("503", "429", "unavailable", "high demand", "resource_exhausted")))
            if transient and attempt == 0:
                time.sleep(0.35 + random.uniform(0, 0.15))
                continue
            logger.warning("CivicFlow chat provider error (%s): %s", status, type(exc).__name__)
            if transient:
                raise HTTPException(status_code=503, detail="AI service is temporarily busy.") from None
            raise HTTPException(status_code=502, detail="AI support response failed.") from None
