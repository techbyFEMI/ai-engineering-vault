"""
nodes/classify_intent.py — Classify what the customer actually wants.

This is the first node every incoming message passes through.
The LLM reads the message + conversation history and outputs one of the
defined intents. All subsequent routing decisions are based on this.
"""

import json
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import ConversationState, Intent
from src.llm import get_llm
from src.config_loader import get_business_name

logger = logging.getLogger(__name__)

VALID_INTENTS = [
    "product_enquiry",
    "complaint",
    "negotiation",
    "booking_request",
    "greeting",
    "off_topic",
    "unknown",
]


def classify_intent(state: ConversationState) -> dict:
    """
    Node: Classify the intent of the latest customer message.
    Returns a dict with the 'intent' key to update the state.
    """
    business_name = get_business_name()
    latest_message = state["latest_user_message"]

    # Build context from last 4 turns (avoid bloating the prompt)
    recent_history = state.get("messages", [])[-8:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_history
    ) or "No prior conversation."

    system_prompt = f"""You are a message classifier for {business_name}'s WhatsApp sales agent.

Your ONLY job is to classify the customer's latest message into one of these intents:
- product_enquiry: asking about products, services, prices, availability, features
- complaint: expressing dissatisfaction, reporting a problem, or frustrated
- negotiation: trying to get a lower price, better deal, or discount
- booking_request: wants to book an appointment, visit, or schedule something
- greeting: just saying hi, hello, or starting a conversation
- off_topic: clearly unrelated to the business
- unknown: message is ambiguous or you genuinely cannot determine intent

Respond with ONLY a JSON object in this exact format — no extra text:
{{"intent": "<one of the intents above>", "confidence": "<high|medium|low>", "reasoning": "<one sentence>"}}"""

    user_prompt = f"""Conversation history:
{history_text}

Customer's latest message: "{latest_message}"

Classify the intent."""

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        # Parse the JSON response
        raw = response.content.strip()
        # Handle markdown code fences if the model wraps it
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        parsed = json.loads(raw.strip())
        intent = parsed.get("intent", "unknown")

        if intent not in VALID_INTENTS:
            logger.warning(f"LLM returned unknown intent '{intent}', defaulting to 'unknown'")
            intent = "unknown"

        logger.info(f"[{state['customer_phone']}] Intent: {intent} ({parsed.get('confidence', '?')}) — {parsed.get('reasoning', '')}")

        return {
            "intent": intent,
            "turn_count": state.get("turn_count", 0) + 1,
        }

    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Intent classification parsing failed: {e}. Defaulting to 'unknown'.")
        return {
            "intent": "unknown",
            "turn_count": state.get("turn_count", 0) + 1,
        }
    except Exception as e:
        logger.error(f"Intent classification LLM call failed: {e}")
        return {
            "intent": "unknown",
            "turn_count": state.get("turn_count", 0) + 1,
        }
