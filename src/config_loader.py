"""
config_loader.py — Loads and validates the business_config.yaml.

This is the "product" part of the system — every client gets their own
YAML file. You swap the file, restart the server, and the agent transforms
into their brand, their products, their guardrails. No code changes needed.
"""

import os
import yaml
from pathlib import Path
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def load_config() -> dict:
    """Load and cache the business configuration from YAML."""
    config_path = os.getenv("BUSINESS_CONFIG_PATH", "config/business_config.yaml")
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Business config not found at '{config_path}'. "
            "Copy .env.example to .env and set BUSINESS_CONFIG_PATH."
        )

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    _validate_config(config)
    return config


def _validate_config(config: dict) -> None:
    """Raise clear errors if critical config keys are missing."""
    required_keys = ["business.name", "business.products", "business.guardrails"]
    for key_path in required_keys:
        keys = key_path.split(".")
        obj = config
        for k in keys:
            if not isinstance(obj, dict) or k not in obj:
                raise ValueError(
                    f"Missing required config key: '{key_path}'. "
                    "Check your business_config.yaml."
                )
            obj = obj[k]


def get_business_name() -> str:
    return load_config()["business"]["name"]


def get_products() -> list[dict]:
    return load_config()["business"]["products"]


def get_faq() -> list[dict]:
    return load_config()["business"].get("faq", [])


def get_guardrails() -> dict:
    return load_config()["business"]["guardrails"]


def get_tone() -> str:
    return load_config()["business"].get("tone", "professional and friendly")


def get_closing_goal() -> str:
    return load_config()["business"].get("closing_goal", "close a sale or book a meeting")


def get_escalate_after_turns() -> int:
    return get_guardrails().get("escalate_after_turns", 8)


def get_escalate_notify_number() -> str:
    return get_guardrails().get("escalate_notify_number", "")


def build_products_summary() -> str:
    """Build a readable product list string for the LLM system prompt."""
    products = get_products()
    lines = []
    for p in products:
        if not p.get("available", True):
            continue
        currency = p.get("currency", "NGN")
        price_min = f"{p['price_min']:,}"
        price_max = f"{p['price_max']:,}"
        lines.append(
            f"- {p['name']}: {currency} {price_min} – {price_max}. {p['description']}"
        )
    return "\n".join(lines)


def build_faq_summary() -> str:
    """Build a readable FAQ string for the LLM system prompt."""
    faq = get_faq()
    if not faq:
        return "No specific FAQs configured."
    lines = []
    for item in faq:
        lines.append(f"Q: {item['q']}\nA: {item['a']}")
    return "\n\n".join(lines)
