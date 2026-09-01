import os
import traceback

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai


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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. Add it to your .env file."
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ================= AI SUPPORT CHAT =================

@router.post("/chat")
def chat_with_support(request: ChatRequest):

    try:

        prompt = f"""
You are CivicFlow AI Support Assistant.

CivicFlow is an AI-powered Intelligent Public Service Management System.

Your job is to help citizens understand and use the CivicFlow platform.

CivicFlow features include:

- Lodging public grievances
- AI-based department classification
- Complaint priority prediction
- AI-generated complaint summaries
- Multilingual complaint support
- Complaint tracking
- Complaint statuses such as Assigned, In Progress, Resolved and Rejected
- Location-based complaint information
- Government department routing

Rules:

1. Be friendly and helpful.
2. Give clear and concise answers.
3. Answer mainly about CivicFlow and public grievance usage.
4. Do not invent information about the user's personal complaint.
5. If asked about government information that you don't know, clearly say so.
6. Do not claim that you can directly change or resolve complaints.
7. Keep responses reasonably short and easy for citizens to understand.

User question:

{request.message}
"""

        response = client.models.generate_content(

            model="gemini-3.6-flash",

            contents=prompt

        )


        reply = response.text


        if not reply:

            reply = (
                "Sorry, I couldn't generate a response. "
                "Please try again."
            )


        return {
            "reply": reply
        }


    except Exception as e:

        print("\n========== GEMINI ERROR ==========")

        print(str(e))

        traceback.print_exc()

        print("==================================\n")


        raise HTTPException(

            status_code=500,

            detail=str(e)

        )