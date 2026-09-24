"""
nodes/apply_guardrails.py — The safety layer between draft and send.

This node checks every draft reply BEFORE it goes to the customer.
It enforces the business owner's hard rules: forbidden phrases, price floors,
and any content policies. If a violation is found, it either patches the reply
automatically or triggers escalation.

This is one of the key selling points of LangGraph over n8n/Make:
you get a programmable, auditable safety layer that never sends
an unauthorized reply.
"""

import re
import logging
from src.state import ConversationState
from src.config_loader import get_guardrails, get_products

logger = logging.getLogger(__name__)


def apply_guardrails(state: ConversationState) -> dict:
    """
    Node: Check the draft reply against all configured guardrails.
    
    Returns updated state with:
    - guardrail_triggered: True if any rule fired
    - guardrail_reason: Description of what fired
    - draft_reply: Possibly modified reply (if auto-patchable)
    """
    draft = state.get("draft_reply", "")
    guardrails = get_guardrails()
    products = get_products()

    violations = []
    patched_reply = draft

    # ── Rule 1: Forbidden phrases ─────────────────────────────────────────────
    forbidden_phrases = guardrails.get("forbidden_phrases", [])
    for phrase in forbidden_phrases:
        if phrase.lower() in patched_reply.lower():
            violations.append(f"Forbidden phrase detected: '{phrase}'")
            # Auto-patch: remove the offending phrase
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            patched_reply = pattern.sub("[removed]", patched_reply)
            logger.warning(f"[{state['customer_phone']}] Guardrail: forbidden phrase '{phrase}' found and removed")

    # ── Rule 2: Price floor enforcement ──────────────────────────────────────
    # Check if any quoted number is suspiciously low (below any product's min price)
    # Extract all numbers from the reply
    quoted_numbers = [int(n.replace(",", "").replace("_", "")) for n in re.findall(r"[\d,_]{6,}", patched_reply)]
    
    for product in products:
        price_min = product.get("price_min", 0)
        currency = product.get("currency", "NGN")
        
        for quoted in quoted_numbers:
            if 0 < quoted < price_min:
                violations.append(
                    f"Price floor violation: quoted {currency} {quoted:,} is below minimum {currency} {price_min:,} for '{product['name']}'"
                )
                logger.error(
                    f"[{state['customer_phone']}] PRICE FLOOR VIOLATION: "
                    f"Reply quoted {quoted:,} which is below floor {price_min:,}"
                )

    # ── Rule 3: Maximum discount enforcement ─────────────────────────────────
    max_discount = guardrails.get("max_discount_percent", 0)
    if max_discount == 0:
        # If no discounts allowed at all, flag any discount language
        discount_patterns = [r"\d+\s*%\s*off", r"discount", r"reduce the price", r"lower the price"]
        for pattern in discount_patterns:
            if re.search(pattern, patched_reply, re.IGNORECASE):
                violations.append(f"Discount language found but no discounts are authorized for this business")
                logger.warning(f"[{state['customer_phone']}] Guardrail: discount language in reply, no discounts authorized")
                break

    # ── Rule 4: Reply length check ────────────────────────────────────────────
    if len(patched_reply) > 1500:
        violations.append("Reply exceeds WhatsApp-friendly length (>1500 chars)")
        # Auto-truncate at sentence boundary near 1000 chars
        truncated = patched_reply[:1000]
        last_period = truncated.rfind(".")
        if last_period > 500:
            patched_reply = truncated[:last_period + 1]
        logger.warning(f"[{state['customer_phone']}] Guardrail: reply truncated from {len(draft)} to {len(patched_reply)} chars")

    # ── Compile result ────────────────────────────────────────────────────────
    if violations:
        # Price floor violations are severe — trigger escalation instead of sending
        price_violations = [v for v in violations if "price floor" in v.lower()]
        if price_violations:
            return {
                "guardrail_triggered": True,
                "guardrail_reason": " | ".join(violations),
                "draft_reply": (
                    "Thank you for your interest! Let me connect you with our team "
                    "who can provide you with the most accurate pricing details. "
                    "We'll be in touch shortly."
                ),
                "escalation_requested": True,
                "escalation_reason": f"PRICE FLOOR VIOLATION blocked automated reply: {' | '.join(price_violations)}",
            }

        # Minor violations (forbidden phrases, length) — send patched reply
        return {
            "guardrail_triggered": True,
            "guardrail_reason": " | ".join(violations),
            "draft_reply": patched_reply,
            "escalation_requested": state.get("escalation_requested", False),
        }

    # No violations
    logger.info(f"[{state['customer_phone']}] Guardrails passed — reply is clean")
    return {
        "guardrail_triggered": False,
        "guardrail_reason": "",
        "draft_reply": patched_reply,
    }
