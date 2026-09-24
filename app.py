"""
app.py — FastAPI webhook server.

This is the entry point. Meta's WhatsApp Cloud API sends all incoming
messages as HTTP POST requests to your webhook URL.

Two endpoints:
  GET  /webhook  — Verification handshake (Meta calls this once when you set up the webhook)
  POST /webhook  — Incoming messages from customers (called on every new message)

For local development + demo: use ngrok to expose this server to the internet.
  ngrok http 8000
Then set the ngrok HTTPS URL as your webhook in the Meta dashboard.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse, JSONResponse
from dotenv import load_dotenv
from src.graph import get_graph
from src.whatsapp import mark_as_read

load_dotenv()

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── App Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-build the graph on startup so the first message isn't slow."""
    logger.info("🚀 Starting LangGraph WhatsApp Agent...")
    get_graph()  # Build and cache the graph
    logger.info("✅ Graph compiled. Ready to receive messages.")
    yield
    logger.info("👋 Shutting down.")


app = FastAPI(
    title="LangGraph WhatsApp Sales Agent",
    description="AI-powered WhatsApp sales agent for business owners",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Webhook Verification ──────────────────────────────────────────────────────
@app.get("/webhook")
async def verify_webhook(request: Request):
    """
    Meta calls this endpoint once when you configure the webhook.
    It sends a challenge token that you must echo back to prove you own the server.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    if mode == "subscribe" and token == expected_token:
        logger.info("✅ Webhook verified by Meta")
        return PlainTextResponse(content=challenge)
    else:
        logger.warning(f"❌ Webhook verification failed. Token: {token}, Mode: {mode}")
        raise HTTPException(status_code=403, detail="Verification failed")


# ── Incoming Messages ─────────────────────────────────────────────────────────
@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """
    Meta sends all incoming WhatsApp messages here as JSON payloads.
    We parse the message, then run the LangGraph agent in the background
    so this endpoint returns 200 immediately (Meta requires a fast 200 response).
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Meta sends a test ping with this structure — acknowledge and ignore
    if body.get("object") != "whatsapp_business_account":
        return JSONResponse(content={"status": "ignored"})

    # Parse the message payload
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]["value"]

        # Ignore status updates (delivery receipts, read receipts)
        if "statuses" in change and "messages" not in change:
            return JSONResponse(content={"status": "status_update_ignored"})

        messages = change.get("messages", [])
        if not messages:
            return JSONResponse(content={"status": "no_message"})

        message = messages[0]
        message_type = message.get("type")

        # Only handle text messages for now
        if message_type != "text":
            logger.info(f"Non-text message received ({message_type}), ignoring")
            return JSONResponse(content={"status": "non_text_ignored"})

        customer_phone = message["from"]  # E.164 format: +2348012345678
        message_id = message["id"]
        text = message["text"]["body"]

        # Get customer name from contact info if available
        contacts = change.get("contacts", [])
        customer_name = ""
        if contacts:
            customer_name = contacts[0].get("profile", {}).get("name", "")

        logger.info(f"📩 Message from {customer_phone} ({customer_name}): {text[:80]}")

        # Mark as read immediately (shows blue ticks)
        mark_as_read(message_id)

        # Run the agent graph in the background
        background_tasks.add_task(
            run_agent,
            customer_phone=customer_phone,
            customer_name=customer_name,
            text=text,
            message_id=message_id,
        )

        # Return 200 immediately — Meta requires this within 5 seconds
        return JSONResponse(content={"status": "processing"})

    except (KeyError, IndexError) as e:
        logger.error(f"Failed to parse WhatsApp webhook payload: {e}\nBody: {body}")
        # Still return 200 to avoid Meta retrying
        return JSONResponse(content={"status": "parse_error"})


# ── Agent Runner ──────────────────────────────────────────────────────────────
async def run_agent(customer_phone: str, customer_name: str, text: str, message_id: str):
    """
    Run the LangGraph agent graph for a single incoming message.
    Each customer's conversation is isolated by using their phone number as thread_id.
    """
    graph = get_graph()

    # The config identifies this conversation thread
    # LangGraph uses this to load/save the correct checkpoint
    config = {
        "configurable": {
            "thread_id": customer_phone,  # One memory slot per customer
        }
    }

    # Initial state for this turn — LangGraph merges this with the checkpointed state
    input_state = {
        "customer_phone": customer_phone,
        "customer_name": customer_name,
        "latest_user_message": text,
        "wa_message_id": message_id,
        # These fields will be set by the nodes:
        "intent": "unknown",
        "draft_reply": "",
        "guardrail_triggered": False,
        "guardrail_reason": "",
        "escalation_requested": False,
        "escalation_reason": "",
        "closing_achieved": False,
        # These are Annotated[list, add] — they accumulate across turns:
        "messages": [],
        "products_mentioned": [],
        # Turn count is incremented by classify_intent
        "turn_count": 0,
    }

    try:
        # Run the graph — this blocks until the graph reaches END
        result = await asyncio.to_thread(
            graph.invoke,
            input_state,
            config=config,
        )
        logger.info(
            f"[{customer_phone}] Graph completed. "
            f"Intent: {result.get('intent')} | "
            f"Guardrail: {result.get('guardrail_triggered')} | "
            f"Escalated: {result.get('escalation_requested')}"
        )
    except Exception as e:
        logger.error(f"[{customer_phone}] Graph execution failed: {e}", exc_info=True)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """Simple health check — useful for monitoring."""
    from src.config_loader import get_business_name
    return {
        "status": "ok",
        "business": get_business_name(),
        "agent": "LangGraph WhatsApp Sales Agent v1.0",
    }


# ── Run directly with: python app.py ─────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
