"""
AI Service
──────────
Wraps the LLM API call.
Supports both Anthropic (Claude) and OpenAI (GPT-4o).
Set AI_PROVIDER=anthropic or AI_PROVIDER=openai in your .env file.
"""

import os
import httpx
import json
from typing import Optional


SYSTEM_PROMPT = """You are Aria, a warm, intelligent customer support assistant.

Your job:
- Help customers with their orders, billing, accounts, and technical issues.
- Maintain context from earlier in the conversation — never ask for information the customer already gave you.
- Be concise but empathetic. Never robotic.
- If you detect frustration or a complaint, acknowledge it first before solving.
- If a customer asks to speak to a human, respond with:
  "I completely understand. Let me connect you with one of our support agents right away.
   Please hold for a moment. [ESCALATE]"
- Use the customer's name when you know it.
- Never make up order details, shipping dates, or policies. If you don't know, say:
  "Let me check that for you — could you confirm your order ID so I can pull up the details?"

Tone: Friendly, professional, solutions-first. Like the best support rep you've ever spoken to."""


class AIService:

    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER", "anthropic").lower()
        self.api_key  = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError(
                "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY in your .env file."
            )

    async def generate_reply(
        self,
        history: list[dict],
        context_summary: dict,
        intent: str
    ) -> str:

        # Inject context as extra system information
        context_note = self._build_context_note(context_summary, intent)

        if self.provider == "anthropic":
            return await self._call_anthropic(history, context_note)
        else:
            return await self._call_openai(history, context_note)

    # ── Anthropic ─────────────────────────────────────────────────────────────

    async def _call_anthropic(self, history: list[dict], context_note: str) -> str:
        system = SYSTEM_PROMPT + "\n\n" + context_note

        # Separate system messages from conversation turns
        messages = [m for m in history if m["role"] != "system"]

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-sonnet-4-5",
                    "max_tokens": 1024,
                    "system":     system,
                    "messages":   messages,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]

    # ── OpenAI ────────────────────────────────────────────────────────────────

    async def _call_openai(self, history: list[dict], context_note: str) -> str:
        system = SYSTEM_PROMPT + "\n\n" + context_note

        messages = [{"role": "system", "content": system}]

        # Merge any injected system turns from history
        for m in history:
            if m["role"] == "system":
                messages[0]["content"] += "\n\n" + m["content"]
            else:
                messages.append(m)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       "gpt-4o",
                    "messages":    messages,
                    "max_tokens":  1024,
                    "temperature": 0.7,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_context_note(self, summary: dict, intent: str) -> str:
        lines = [f"[Live session context]"]
        lines.append(f"Customer name : {summary.get('user_name', 'Unknown')}")
        lines.append(f"Current intent: {intent}")
        lines.append(f"Turn number   : {summary.get('turn_count', 0)}")

        entities = summary.get("entities", {})
        if entities:
            entity_str = ", ".join(f"{k}={v}" for k, v in entities.items())
            lines.append(f"Known entities: {entity_str}")

        topics = summary.get("topic_history", [])
        if topics:
            lines.append(f"Topics so far : {' → '.join(topics)}")

        return "\n".join(lines)
