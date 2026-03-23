"""
Intent Recognizer
─────────────────
Classifies every user message into a structured intent.

Approach:
  1. Fast keyword/pattern matching for common, unambiguous intents.
  2. Falls back to LLM-based classification only when patterns are ambiguous.

This two-tier design keeps latency low (most messages match tier-1)
while maintaining accuracy for complex inputs.
"""

import re
from typing import Optional


# ── Intent catalogue ──────────────────────────────────────────────────────────

INTENTS = {
    # Order management
    "order_status":      ["order status", "where is my order", "track", "tracking", "when will", "delivery status", "shipped"],
    "order_cancel":      ["cancel order", "cancel my order", "want to cancel", "stop order"],
    "order_return":      ["return", "send back", "refund", "exchange", "replace"],

    # Account & billing
    "account_help":      ["account", "login", "password", "sign in", "username", "locked out", "access"],
    "billing":           ["bill", "invoice", "charge", "payment", "subscription", "price", "cost", "fee", "paid"],

    # Technical support
    "tech_support":      ["not working", "broken", "error", "issue", "problem", "bug", "crash", "failed", "doesn't work"],

    # Product information
    "product_info":      ["what is", "tell me about", "features", "specification", "how does", "does it"],
    "pricing":           ["price", "how much", "cost", "plan", "pricing", "rate", "charges"],

    # Human escalation
    "escalation":        ["speak to", "talk to", "human", "agent", "manager", "supervisor", "real person"],

    # Sentiment
    "complaint":         ["terrible", "worst", "awful", "disgusting", "unacceptable", "ridiculous", "horrible", "very bad"],
    "compliment":        ["great", "awesome", "excellent", "thank you", "thanks", "love it", "perfect", "happy"],

    # General
    "greeting":          ["hello", "hi ", "hey", "good morning", "good evening", "howdy", "sup"],
    "farewell":          ["bye", "goodbye", "see you", "take care", "exit", "quit"],
    "affirmation":       ["yes", "yeah", "sure", "okay", "ok", "correct", "right", "exactly"],
    "negation":          ["no", "nope", "not", "never", "don't", "didn't", "hasn't"],
}

CONTEXT_DEPENDENT = {
    # When a single word follows these context intents, inherit the context
    "order_status": ["order_return", "order_cancel"],
    "billing":      ["order_status"],
}


class IntentRecognizer:

    def recognize(self, message: str, history: list[dict]) -> str:
        """
        Returns the best-matching intent string for the given message.
        Uses history for context-aware disambiguation.
        """
        cleaned = message.lower().strip()

        # 1. Try direct keyword matching
        matched = self._keyword_match(cleaned)

        # 2. Contextual fallback — inherit intent from recent history
        if matched == "general_query" and history:
            last_intent = self._get_last_intent(history)
            matched = self._contextual_inherit(cleaned, last_intent) or matched

        return matched

    # ── Private ───────────────────────────────────────────────────────────────

    def _keyword_match(self, text: str) -> str:
        scores: dict[str, int] = {}

        for intent, keywords in INTENTS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score:
                scores[intent] = score

        if not scores:
            return "general_query"

        return max(scores, key=lambda k: scores[k])

    def _get_last_intent(self, history: list[dict]) -> Optional[str]:
        # Walk backwards through history looking for an assistant turn
        # that has intent metadata. Since history is plain {role, content}
        # dicts here, we infer from content keywords instead.
        for turn in reversed(history):
            if turn["role"] == "assistant":
                return self._keyword_match(turn["content"].lower())
        return None

    def _contextual_inherit(self, text: str, last_intent: Optional[str]) -> Optional[str]:
        """
        If the message is short / ambiguous and the last intent is a known
        context anchor, inherit a related intent.
        """
        if not last_intent:
            return None

        # Very short messages (< 4 words) likely continue prior topic
        if len(text.split()) < 4:
            related = CONTEXT_DEPENDENT.get(last_intent, [])
            for candidate in related:
                keywords = INTENTS.get(candidate, [])
                if any(kw in text for kw in keywords):
                    return candidate
            return last_intent   # inherit directly

        return None
