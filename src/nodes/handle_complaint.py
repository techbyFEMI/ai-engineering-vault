"""
nodes/handle_complaint.py — Handle complaints empathetically without overpromising.

When a customer is frustrated or has a problem, the agent must:
1. Acknowledge and empathize (never be defensive)
2. Offer a concrete next step within the business's authority
3. Escalate if the issue is beyond what the agent can resolve

This node is careful not to make commitments the business hasn't authorized.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import ConversationState
from src.llm import get_llm
from src.config_loader import get_business_name, get_tone, get_guardrails

logger = logging.getLogger(__name__)


def handle_complaint(state: ConversationState) -> dict:
    """
    Node: Generate an empathetic, action-oriented reply to a complaint.
    """
    business_name = get_business_name()
    tone = get_tone()
    guardrails = get_guardrails()
    forbidden = ", ".join(f'"{p}"' for p in guardrails.get("forbidden_phrases", []))
    escalate_after = guardrails.get("escalate_after_turns", 8)
    current_turn = state.get("turn_count", 1)

    recent_history = state.get("messages", [])[-10:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_history
    ) or "This is the first message."

    # If the customer has been complaining for many turns without resolution,
    # flag for human escalation
    if current_turn >= escalate_after:
        logger.info(f"[{state['customer_phone']}] Complaint reached turn limit, flagging for escalation")
        return {
            "draft_reply": (
                f"I sincerely apologize for the inconvenience. "
                f"I'm connecting you with a senior member of our team at {business_name} "
                f"who will reach out to you very shortly to resolve this personally. "
                f"Thank you for your patience."
            ),
            "escalation_requested": True,
            "escalation_reason": f"Customer complaint unresolved after {current_turn} turns",
            "guardrail_triggered": False,
            "guardrail_reason": "",
        }

    system_prompt = f"""You are a customer care agent for {business_name}.
Your tone is {tone} — but when handling complaints, prioritize being warm, calm, and empathetic above all else.

YOUR RULES FOR HANDLING COMPLAINTS:
1. Always start by acknowledging the customer's frustration — never be defensive
2. Apologize sincerely but without admitting legal liability (avoid "it's our fault")
3. Offer a clear, actionable next step (schedule a call, provide a contact, clarify a process)
4. NEVER use these phrases: {forbidden}
5. NEVER promise refunds, replacements, or compensation unless it's listed in the FAQ
6. Keep the reply to 4-6 sentences — don't overwhelm a frustrated customer with walls of text
7. End with an offer to help further or a specific next step

Remember: your goal is to de-escalate and rebuild trust."""

    user_prompt = f"""Conversation so far:
{history_text}

Customer's complaint: "{state['latest_user_message']}"

Write a calm, empathetic reply that acknowledges their concern and offers a concrete next step."""

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        draft = response.content.strip()
        logger.info(f"[{state['customer_phone']}] Complaint handler drafted reply")

        return {
            "draft_reply": draft,
            "escalation_requested": False,
            "escalation_reason": "",
            "guardrail_triggered": False,
            "guardrail_reason": "",
        }

    except Exception as e:
        logger.error(f"handle_complaint LLM call failed: {e}")
        return {
            "draft_reply": (
                f"We're really sorry to hear about your experience. "
                f"A member of the {business_name} team will follow up with you shortly "
                f"to make sure this is resolved. Thank you for bringing it to our attention."
            ),
            "escalation_requested": True,
            "escalation_reason": "LLM failure during complaint handling",
            "guardrail_triggered": False,
            "guardrail_reason": "",
        }
