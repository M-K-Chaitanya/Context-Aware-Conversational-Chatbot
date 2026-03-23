from datetime import datetime
from typing import Optional


class Turn:
    def __init__(self, role: str, content: str, intent: str, timestamp: str):
        self.role      = role
        self.content   = content
        self.intent    = intent
        self.timestamp = timestamp

    def to_dict(self):
        return {
            "role":      self.role,
            "content":   self.content,
            "intent":    self.intent,
            "timestamp": self.timestamp,
        }


class ContextManager:
    """
    Maintains full conversation history, extracted entities, and
    a rolling context window for long conversations.

    Design principles:
      - Keep the last MAX_TURNS turns in active memory.
      - Beyond that, summarise older turns into a compact context block.
      - Track named entities (order IDs, product names, etc.) across turns.
      - Expose a clean message list that the LLM can consume directly.
    """

    MAX_TURNS = 20   # keep last 20 turns in full; summarise earlier ones

    def __init__(self, session_id: str, user_name: str = "User"):
        self.session_id  = session_id
        self.user_name   = user_name
        self.turns: list[Turn] = []
        self.entities: dict    = {}   # e.g. {"order_id": "ORD-123", "product": "AirPods"}
        self.topic_history: list[str] = []
        self.created_at  = datetime.utcnow().isoformat()
        self.turn_count  = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def add_turn(self, role: str, content: str, intent: str):
        turn = Turn(
            role=role,
            content=content,
            intent=intent,
            timestamp=datetime.utcnow().isoformat()
        )
        self.turns.append(turn)
        self.turn_count += 1

        # Track topic shifts
        if role == "user" and intent not in self.topic_history[-3:]:
            self.topic_history.append(intent)

        # Extract entities from user messages
        if role == "user":
            self._extract_entities(content)

    def get_history(self) -> list[dict]:
        """
        Returns the last MAX_TURNS as a list of {role, content} dicts
        ready to pass to the LLM. Older turns are condensed into a
        system summary injected at position 0.
        """
        recent = self.turns[-self.MAX_TURNS:]

        messages = []

        # Inject condensed summary of older turns if they exist
        if len(self.turns) > self.MAX_TURNS:
            older = self.turns[:-self.MAX_TURNS]
            summary_text = self._condense_older_turns(older)
            messages.append({
                "role": "system",
                "content": f"[Earlier conversation summary]\n{summary_text}"
            })

        messages += [{"role": t.role, "content": t.content} for t in recent]
        return messages

    def get_summary(self) -> dict:
        return {
            "session_id":    self.session_id,
            "user_name":     self.user_name,
            "turn_count":    self.turn_count,
            "entities":      self.entities,
            "topic_history": self.topic_history[-5:],
            "last_intent":   self.turns[-1].intent if self.turns else "unknown",
            "created_at":    self.created_at,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _extract_entities(self, text: str):
        """
        Lightweight regex-free entity extraction.
        In production you would use spaCy NER or a dedicated LLM call.
        """
        import re

        # Order IDs like ORD-12345 or #12345
        order_match = re.search(r'\b(ORD[-#]?\d{4,})\b', text, re.IGNORECASE)
        if order_match:
            self.entities["order_id"] = order_match.group(1).upper()

        # Email addresses
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[a-z]{2,}', text)
        if email_match:
            self.entities["email"] = email_match.group(0)

        # Phone numbers (Indian format)
        phone_match = re.search(r'\b[6-9]\d{9}\b', text)
        if phone_match:
            self.entities["phone"] = phone_match.group(0)

        # Simple product name hints
        products = ["iphone", "samsung", "laptop", "airpods", "macbook",
                    "subscription", "plan", "account", "invoice"]
        for prod in products:
            if prod in text.lower() and "product" not in self.entities:
                self.entities["product"] = prod

    def _condense_older_turns(self, turns: list[Turn]) -> str:
        lines = []
        for t in turns:
            speaker = self.user_name if t.role == "user" else "Assistant"
            lines.append(f"{speaker}: {t.content[:120]}{'...' if len(t.content) > 120 else ''}")
        return "\n".join(lines)
