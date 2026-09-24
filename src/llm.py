"""
llm.py — LLM client configured for OpenRouter's free API.

OpenRouter exposes an OpenAI-compatible API, so we use LangChain's
ChatOpenAI with a custom base_url. This means we can swap to any
model on OpenRouter (including free ones) by just changing MODEL_NAME.

Free models available on OpenRouter as of late 2024:
  - meta-llama/llama-3.1-8b-instruct:free
  - mistralai/mistral-7b-instruct:free
  - google/gemma-2-9b-it:free
  - microsoft/phi-3-mini-128k-instruct:free
"""

import os
from functools import lru_cache
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Uses OpenRouter's auto-router — automatically routes to an available free model
MODEL_NAME = "openrouter/auto"


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Return a cached LangChain LLM client pointed at OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file.\n"
            "Get a free key at https://openrouter.ai/keys"
        )

    return ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.4,          # Low temp = more consistent, brand-safe replies
        max_tokens=512,           # WhatsApp messages should be concise
        default_headers={
            # OpenRouter requires these headers to track usage
            "HTTP-Referer": "https://github.com/your-username/langgraph-wa-agent",
            "X-Title": "LangGraph WhatsApp Sales Agent",
        },
    )
