from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
import os
from dotenv import load_dotenv

from core.context_manager import ContextManager
from core.intent_recognizer import IntentRecognizer
from core.ai_service import AIService

load_dotenv()

app = FastAPI(
    title="Aria — Context-Aware Support Chatbot",
    version="1.0.0",
    description="Multi-turn conversational chatbot with context memory and intent recognition"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory session store (use Redis in production)
sessions: dict[str, ContextManager] = {}

ai_service     = AIService()
intent_engine  = IntentRecognizer()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    user_name: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    intent: str
    context_summary: dict
    turn_number: int


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("static/index.html")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # Create or retrieve session
    session_id = req.session_id or str(uuid.uuid4())

    if session_id not in sessions:
        sessions[session_id] = ContextManager(
            session_id=session_id,
            user_name=req.user_name or "User"
        )

    ctx = sessions[session_id]

    # 1. Recognise intent
    intent = intent_engine.recognize(req.message, ctx.get_history())

    # 2. Add user turn to context
    ctx.add_turn(role="user", content=req.message, intent=intent)

    # 3. Build prompt with full context and call AI
    try:
        reply = await ai_service.generate_reply(
            history=ctx.get_history(),
            context_summary=ctx.get_summary(),
            intent=intent
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")

    # 4. Add assistant reply to context
    ctx.add_turn(role="assistant", content=reply, intent=intent)

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        intent=intent,
        context_summary=ctx.get_summary(),
        turn_number=ctx.turn_count
    )


@app.get("/session/{session_id}/history")
async def get_history(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    ctx = sessions[session_id]
    return {
        "session_id": session_id,
        "history": ctx.get_history(),
        "summary": ctx.get_summary(),
        "turn_count": ctx.turn_count
    }


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"message": "Session cleared"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Aria Chatbot"}
