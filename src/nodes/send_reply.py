"""
nodes/send_reply.py — Final node: send the approved reply to the customer.

By the time a message reaches this node, it has passed through:
  classify_intent → handle_* → apply_guardrails

This node:
1. Sends the reply to the customer via WhatsApp
2. If escalation is flagged, notifies the business owner on their personal WhatsApp
3. Updates the conversation history in the state (for memory continuity)
4. Logs the full turn to conversations.jsonl for business owner review
"""

import os
import json
import logging
import datetime
from pathlib import Path
from src.state import ConversationState
from src.whatsapp import send_message, send_escalation_alert
from src.config_loader import get_escalate_notify_number, get_business_name

logger = logging.getLogger(__name__)


def send_reply(state: ConversationState) -> dict:
    """
    Node: Send the final reply and handle any escalation notifications.
    Returns updated messages list to append to conversation history.
    """
    customer_phone = state["customer_phone"]
    draft = state.get("draft_reply", "")
    escalation_requested = state.get("escalation_requested", False)
    escalation_reason = state.get("escalation_reason", "")

    # ── Send the reply to the customer ────────────────────────────────────────
    if draft:
        try:
            send_message(to=customer_phone, text=draft)
            logger.info(f"[{customer_phone}] Reply sent successfully")
        except Exception as e:
            logger.error(f"[{customer_phone}] Failed to send reply: {e}")
            # Don't crash the graph — log it and move on
            draft = "(Reply failed to send)"

    # ── Notify owner if escalation was triggered ───────────────────────────────
    if escalation_requested:
        owner_number = get_escalate_notify_number()
        if owner_number:
            recent_messages = state.get("messages", [])[-4:]
            preview = recent_messages[-1]["content"] if recent_messages else state["latest_user_message"]
            send_escalation_alert(
                owner_number=owner_number,
                customer_phone=customer_phone,
                reason=escalation_reason,
                conversation_preview=preview[:200],
            )
        logger.info(f"[{customer_phone}] Escalation triggered: {escalation_reason}")

    # ── Append this turn to the conversation history ──────────────────────────
    new_messages = [
        {"role": "user", "content": state["latest_user_message"]},
        {"role": "assistant", "content": draft},
    ]

    # ── Log the conversation to JSONL file ────────────────────────────────────
    _log_conversation_turn(state, draft)

    return {
        "messages": new_messages,  # Appended via Annotated[list, add] in state
    }


def _log_conversation_turn(state: ConversationState, sent_reply: str) -> None:
    """Append a log entry to conversations.jsonl for the business owner's review."""
    if os.getenv("ENABLE_LOGGING", "true").lower() != "true":
        return

    log_entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "customer_phone": state.get("customer_phone", "unknown"),
        "customer_name": state.get("customer_name", ""),
        "turn": state.get("turn_count", 0),
        "intent": state.get("intent", "unknown"),
        "customer_message": state.get("latest_user_message", ""),
        "agent_reply": sent_reply,
        "guardrail_triggered": state.get("guardrail_triggered", False),
        "guardrail_reason": state.get("guardrail_reason", ""),
        "escalation": state.get("escalation_requested", False),
        "escalation_reason": state.get("escalation_reason", ""),
        "closing_achieved": state.get("closing_achieved", False),
    }

    log_path = Path("conversations.jsonl")
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write conversation log: {e}")
