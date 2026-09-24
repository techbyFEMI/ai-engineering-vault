"""
nodes/handle_enquiry.py — Handle product enquiries and close toward the sale.

This node activates when the customer is asking about products, prices,
availability, or features. It has full knowledge of the business's product
catalogue, FAQs, and the closing goal, and actively tries to move the
conversation toward a booking or lead capture.
"""

import logging
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import ConversationState
from src.llm import get_llm
from src.config_loader import (
    get_business_name, get_tone, get_closing_goal,
    build_products_summary, build_faq_summary, get_guardrails
)

logger = logging.getLogger(__name__)


def handle_enquiry(state: ConversationState) -> dict:
    """
    Node: Generate a sales-focused reply to a product enquiry.
    The reply will be checked by the guardrail node before sending.
    """
    business_name = get_business_name()
    tone = get_tone()
    closing_goal = get_closing_goal()
    products = build_products_summary()
    faq = build_faq_summary()
    guardrails = get_guardrails()
    forbidden = ", ".join(f'"{p}"' for p in guardrails.get("forbidden_phrases", []))
    max_discount = guardrails.get("max_discount_percent", 0)

    recent_history = state.get("messages", [])[-10:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in recent_history
    ) or "This is the start of the conversation."

    system_prompt = f"""You are a professional sales agent for {business_name}.
Your tone is {tone}.

YOUR PRODUCTS:
{products}

FREQUENTLY ASKED QUESTIONS:
{faq}

YOUR CLOSING GOAL FOR EVERY CONVERSATION:
{closing_goal}

STRICT RULES YOU MUST FOLLOW:
1. Never use these phrases (they are legally/professionally problematic): {forbidden}
2. Never quote a price lower than the listed minimum price for any product
3. If asked for a discount, you may acknowledge flexibility but NEVER commit to more than {max_discount}% off the maximum price
4. Keep replies concise — this is WhatsApp, not email. 3-5 sentences max.
5. Always end with a question that moves the conversation forward
6. If the customer shares their name, use it warmly in the reply
7. Never make up products, features, or information not in the product list above

Your reply will be sent directly to the customer on WhatsApp."""

    user_prompt = f"""Conversation so far:
{history_text}

Customer's latest message: "{state['latest_user_message']}"

Write a helpful, sales-focused reply that moves them toward: {closing_goal}"""

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])

        draft = response.content.strip()
        logger.info(f"[{state['customer_phone']}] Enquiry handler drafted reply ({len(draft)} chars)")

        return {
            "draft_reply": draft,
            "guardrail_triggered": False,
            "guardrail_reason": "",
        }

    except Exception as e:
        logger.error(f"handle_enquiry LLM call failed: {e}")
        fallback = (
            f"Thank you for your interest in {business_name}! "
            "We'd love to help you find the perfect option. "
            "Could you tell us a bit more about what you're looking for?"
        )
        return {
            "draft_reply": fallback,
            "guardrail_triggered": False,
            "guardrail_reason": "",
        }
