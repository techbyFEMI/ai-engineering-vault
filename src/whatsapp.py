"""
whatsapp.py — WhatsApp Cloud API client.

Handles:
  1. Sending text messages to a customer's WhatsApp number
  2. Sending escalation alerts to the business owner
  3. Marking incoming messages as "read" (shows blue ticks)

All API calls go to Meta's WhatsApp Cloud API.
Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages
"""

import os
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WHATSAPP_API_BASE = "https://graph.facebook.com/v20.0"


def _get_headers() -> dict:
    token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not token:
        raise EnvironmentError("WHATSAPP_ACCESS_TOKEN not set in .env")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _get_phone_number_id() -> str:
    pid = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    if not pid:
        raise EnvironmentError("WHATSAPP_PHONE_NUMBER_ID not set in .env")
    return pid


def send_message(to: str, text: str) -> dict:
    """
    Send a WhatsApp text message to `to` (E.164 format, e.g. +2348012345678).
    Returns the API response dict.
    """
    phone_number_id = _get_phone_number_id()
    url = f"{WHATSAPP_API_BASE}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }

    try:
        response = httpx.post(url, json=payload, headers=_get_headers(), timeout=10.0)
        response.raise_for_status()
        logger.info(f"Message sent to {to}: {text[:60]}...")
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"WhatsApp API error sending to {to}: {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"Failed to send WhatsApp message to {to}: {e}")
        raise


def send_escalation_alert(owner_number: str, customer_phone: str, reason: str, conversation_preview: str) -> None:
    """
    Notify the business owner on their own WhatsApp that a conversation needs attention.
    Triggered when the agent decides to escalate.
    """
    message = (
        f"🚨 *Agent Escalation Alert*\n\n"
        f"Customer: {customer_phone}\n"
        f"Reason: {reason}\n\n"
        f"Last message:\n_{conversation_preview}_\n\n"
        f"Please follow up with this customer directly."
    )
    try:
        send_message(owner_number, message)
        logger.info(f"Escalation alert sent to owner at {owner_number}")
    except Exception as e:
        logger.error(f"Failed to send escalation alert to owner: {e}")


def mark_as_read(message_id: str) -> None:
    """Mark an incoming message as read (shows blue ticks to the customer)."""
    phone_number_id = _get_phone_number_id()
    url = f"{WHATSAPP_API_BASE}/{phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    try:
        response = httpx.post(url, json=payload, headers=_get_headers(), timeout=5.0)
        response.raise_for_status()
    except Exception as e:
        # Non-critical — don't crash the flow if read receipt fails
        logger.warning(f"Could not mark message {message_id} as read: {e}")
