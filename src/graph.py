"""
graph.py — The LangGraph StateGraph definition.

This is the brain of the agent. It wires all the nodes together
into a directed graph with conditional routing based on intent.

Graph flow:
  START
    → classify_intent
    → [route by intent]
        product_enquiry / greeting / booking_request / negotiation / unknown
            → handle_enquiry
        complaint
            → handle_complaint
    → apply_guardrails
    → [check escalation]
        escalation_requested=True → send_reply (with owner alert) → END
        escalation_requested=False → send_reply → END

LangGraph's MemorySaver checkpoints the full state after every node,
so each customer's conversation persists across messages automatically.
"""

import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.state import ConversationState
from src.nodes.classify_intent import classify_intent
from src.nodes.handle_enquiry import handle_enquiry
from src.nodes.handle_complaint import handle_complaint
from src.nodes.apply_guardrails import apply_guardrails
from src.nodes.send_reply import send_reply

logger = logging.getLogger(__name__)

# ── Routing Functions ─────────────────────────────────────────────────────────

def route_by_intent(state: ConversationState) -> str:
    """
    Conditional edge: After classify_intent, decide which handler to call.
    Returns the name of the next node.
    """
    intent = state.get("intent", "unknown")
    
    if intent == "complaint":
        return "handle_complaint"
    else:
        # enquiry, greeting, negotiation, booking, unknown → all go to enquiry handler
        # (the enquiry handler is smart enough to handle greetings and bookings)
        return "handle_enquiry"


def check_escalation(state: ConversationState) -> str:
    """
    Conditional edge: After guardrails, decide if we send or escalate.
    Even with escalation, we still send (the node handles both).
    This hook exists for future extension (e.g., pause for human review before sending).
    """
    # Always proceed to send_reply — the node handles escalation notification internally
    return "send_reply"


# ── Build the Graph ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Compile and return the LangGraph StateGraph with in-memory checkpointing.
    
    The checkpointer persists conversation state keyed by thread_id
    (we use the customer's WhatsApp phone number as thread_id).
    This means every customer gets their own isolated, persistent conversation.
    """
    # In-memory checkpointer for development/demo
    # For production, swap this with SqliteSaver or PostgresSaver
    checkpointer = MemorySaver()

    builder = StateGraph(ConversationState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("classify_intent", classify_intent)
    builder.add_node("handle_enquiry", handle_enquiry)
    builder.add_node("handle_complaint", handle_complaint)
    builder.add_node("apply_guardrails", apply_guardrails)
    builder.add_node("send_reply", send_reply)

    # ── Wire edges ────────────────────────────────────────────────────────────
    builder.add_edge(START, "classify_intent")
    
    builder.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "handle_enquiry": "handle_enquiry",
            "handle_complaint": "handle_complaint",
        }
    )
    
    builder.add_edge("handle_enquiry", "apply_guardrails")
    builder.add_edge("handle_complaint", "apply_guardrails")
    
    builder.add_conditional_edges(
        "apply_guardrails",
        check_escalation,
        {"send_reply": "send_reply"}
    )
    
    builder.add_edge("send_reply", END)

    # Compile with checkpointer enabled
    graph = builder.compile(checkpointer=checkpointer)
    logger.info("LangGraph WhatsApp agent graph compiled successfully")
    return graph


# Singleton graph instance — built once, reused per request
_graph_instance = None

def get_graph() -> StateGraph:
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_graph()
    return _graph_instance
