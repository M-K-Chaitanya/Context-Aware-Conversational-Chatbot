# Aria — Context-Aware AI Support Chatbot

A production-grade conversational chatbot built with **FastAPI + Claude/GPT-4o**.  
Maintains full multi-turn context, recognises user intent, extracts entities, and handles coherent dialogue like a real support assistant.

---

## What Makes This Different

Most chatbot demos just pipe messages to an LLM and call it done.  
This project is built the way a real company would build it:

| Feature | What It Does |
|---|---|
| **Context Window Management** | Keeps last 20 turns in full; condenses older turns into a summary injected into every LLM call |
| **Entity Extraction** | Automatically picks up order IDs, emails, phone numbers from conversation |
| **Intent Recognition** | Two-tier system — fast keyword matching + contextual inheritance for ambiguous messages |
| **Fallback Handling** | If the AI call fails, returns a graceful error message instead of crashing |
| **Session Management** | Each user gets a session ID; full history retrievable via REST API |
| **Provider Agnostic** | Swap Claude ↔ GPT-4o by changing one env variable |

---

## Project Structure

```
aria-chatbot/
├── main.py                   # FastAPI app, routes, session store
├── core/
│   ├── context_manager.py    # Multi-turn memory, entity extraction
│   ├── intent_recognizer.py  # Two-tier intent classification
│   └── ai_service.py         # Claude / OpenAI API wrapper
├── static/
│   └── index.html            # Chat UI (single file, no build step)
├── requirements.txt
├── .env.example
├── Procfile                  # For Railway / Render deployment
└── README.md
```

---

## Local Setup

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/aria-chatbot.git
cd aria-chatbot

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your API key

# 5. Run
uvicorn main:app --reload --port 8000

# 6. Open browser
# http://localhost:8000
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `AI_PROVIDER` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` | Your Claude API key from console.anthropic.com |
| `OPENAI_API_KEY` | Your OpenAI key (only if using GPT-4o) |

---

## API Reference

### POST /chat
Send a message and receive a reply with context metadata.

**Request:**
```json
{
  "session_id": "optional-existing-session-id",
  "message": "Where is my order ORD-12345?",
  "user_name": "Riya"
}
```

**Response:**
```json
{
  "session_id": "abc-123",
  "reply": "Hi Riya! Let me look up order ORD-12345 for you...",
  "intent": "order_status",
  "turn_number": 3,
  "context_summary": {
    "user_name": "Riya",
    "turn_count": 3,
    "entities": { "order_id": "ORD-12345" },
    "topic_history": ["greeting", "order_status"],
    "last_intent": "order_status"
  }
}
```

### GET /session/{session_id}/history
Returns full conversation history and context for a session.

### DELETE /session/{session_id}
Clears a session and all its context.

### GET /health
Health check endpoint.

---

## How Context Memory Works

```
Turn 1:  User: "Hi, I'm having an issue with my order"
         → Intent: order_status, entity extraction starts

Turn 2:  User: "It's ORD-78291"
         → Entity extracted: order_id = ORD-78291
         → Context inherits order_status intent

Turn 3:  User: "I want to return it"
         → Intent: order_return
         → order_id already known — agent doesn't ask again

Turn 4:  User: "yes"
         → Short message → contextual inheritance → return confirmed
```

The `ContextManager` maintains this across ALL turns without the LLM needing to re-read the full raw history every time. Older turns beyond 20 are condensed into a compact summary.

---

## Intent Categories

| Intent | Triggers |
|---|---|
| `order_status` | track, where is my order, delivery |
| `order_return` | return, refund, exchange |
| `order_cancel` | cancel order |
| `billing` | invoice, charge, payment, subscription |
| `tech_support` | not working, error, broken |
| `escalation` | speak to human, manager, agent |
| `complaint` | terrible, awful, unacceptable |
| `greeting` | hi, hello, hey |
| `farewell` | bye, goodbye |

---

## Deploy to Railway (Free)

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and deploy
railway login
railway init
railway up

# 3. Set environment variables in Railway dashboard
# AI_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your-key
```

Or deploy to **Render** — connect your GitHub repo, set env vars, done.

---

## Sample Conversations

**Order Tracking:**
```
User:  Where is my order?
Aria:  I'd be happy to help track your order! Could you share your order ID?
User:  ORD-56789
Aria:  Got it! Let me check ORD-56789 for you right away...
User:  Actually I want to cancel it
Aria:  I can help you cancel ORD-56789. Are you sure you'd like to proceed?
```
*(Notice Aria remembers ORD-56789 and doesn't ask again)*

**Frustrated Customer:**
```
User:  This is absolutely terrible. My package has been lost for 2 weeks.
Aria:  I'm really sorry to hear that — a 2-week delay is completely unacceptable
       and I completely understand your frustration. Let me prioritise this
       for you right now. Could you share your order number?
```

---

## Tech Stack

- **Backend:** FastAPI (Python)
- **AI:** Anthropic Claude Sonnet / OpenAI GPT-4o
- **Context:** Custom in-memory ContextManager (Redis-ready)
- **Frontend:** Vanilla HTML/CSS/JS (zero build step)
- **Deploy:** Railway / Render / any Python host
