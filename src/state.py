"""
state.py — Conversation state schema for the LangGraph WhatsApp Agent.

Every node in the graph reads from and writes to this TypedDict.
LangGraph's MemorySaver persists the state per conversation thread
(keyed by the customer's WhatsApp number), so each customer gets
their own isolated, persistent conversation history.
"""

from typing import TypedDict, Annotated, Literal
from operator import add


# ─── Intent Classification ────────────────────────────────────────────────────

Intent = Literal[
    "product_enquiry",   # Asking about products, prices, availability
    "complaint",         # Expressing dissatisfaction or a problem
    "negotiation",       # Trying to get a discount or better deal
    "booking_request",   # Wants to book a visit / appointment
    "greeting",          # Hello, hi, etc — conversation opener
    "off_topic",         # Unrelated to the business
    "unknown",           # Can't determine
]


# ─── Conversation State ───────────────────────────────────────────────────────

class ConversationState(TypedDict):
    """
    The full state of a single customer conversation.
    This object is checkpointed by LangGraph after every node execution,
    so the agent can resume any conversation exactly where it left off.
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    customer_phone: str          # WhatsApp number (used as thread ID)
    customer_name: str           # Filled in once we learn their name

    # ── Conversation History ──────────────────────────────────────────────────
    # Using Annotated + add so LangGraph appends to the list instead of replacing
    messages: Annotated[list[dict], add]   # [{"role": "user"|"assistant", "content": "..."}]
    turn_count: int              # Incremented each round — used for escalation trigger

    # ── Current Turn Input ────────────────────────────────────────────────────
    latest_user_message: str     # The raw message just received from the customer
    intent: Intent               # Classified intent of the latest message

    # ── Sales Tracking ────────────────────────────────────────────────────────
    products_mentioned: Annotated[list[str], add]  # Product IDs discussed so far
    closing_achieved: bool       # True once booking / lead info collected

    # ── Guardrail State ───────────────────────────────────────────────────────
    draft_reply: str             # Reply drafted by the handler node
    guardrail_triggered: bool    # True if a guardrail fired on the draft
    guardrail_reason: str        # Human-readable reason the guardrail fired

    # ── Escalation ────────────────────────────────────────────────────────────
    escalation_requested: bool   # True when agent decides to hand off to human
    escalation_reason: str       # Why escalation was triggered

    # ── Metadata ──────────────────────────────────────────────────────────────
    wa_message_id: str           # WhatsApp message ID of the incoming message
