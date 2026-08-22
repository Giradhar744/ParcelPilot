"""
llm.py — LangChain-based LLM fallback chain.

All providers implement LangChain's BaseChatModel interface, so:
  - Every provider is called identically via .bind_tools().invoke()
  - Adding a new provider (Claude, Gemini, Mistral, etc.) = 2 lines here, zero changes elsewhere
  - Tool calls are returned as LangChain AIMessage objects — uniform format across all providers

Current chain: ChatGroq (primary) → ChatOpenAI@NVIDIA NIM (fallback)

To add a new provider in future:
  1. pip install langchain-<provider>
  2. Instantiate the model and append to PROVIDERS list — done.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

if TYPE_CHECKING:
    # Only imported during type-checking, not at runtime — avoids lint noise
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import BaseMessage

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# ── Provider registry ─────────────────────────────────────────────────────────
# Each entry: (name: str, model: BaseChatModel)
# To add a new provider — e.g. Anthropic:
#   from langchain_anthropic import ChatAnthropic
#   ("anthropic", ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=...))

# list of (provider_name, LangChain chat model)
# To add a new provider: append a new tuple here — zero other changes needed
PROVIDERS: list[tuple[str, Any]] = [
    (
        "groq",
        ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=GROQ_API_KEY,
            temperature=0.3,
        ),
    ),
    (
        "nvidia",
        # NVIDIA NIM is OpenAI-compatible → use ChatOpenAI with custom base_url
        ChatOpenAI(
            model="meta/llama-3.3-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=NVIDIA_API_KEY,
            temperature=0.3,
        ),
    ),
]


# Thread-safe tracker for the active provider index
_provider_index_lock = threading.Lock()
_preferred_provider_index = 0


def call_llm_with_fallback(
    messages: list[Any],
    tools: list[dict] | None = None,
) -> Any:
    """
    Try each provider in order starting from the preferred provider.
    Return the first successful AIMessage and update the preferred provider.

    Args:
        messages: LangChain message objects (SystemMessage, HumanMessage, etc.)
        tools:    OpenAI-format tool schemas (list of dicts with 'type'/'function')

    Returns:
        AIMessage — uniform format regardless of which provider answered.

    Raises:
        RuntimeError if all providers fail.
    """
    global _preferred_provider_index
    num_providers = len(PROVIDERS)
    last_error = None

    with _provider_index_lock:
        start_idx = _preferred_provider_index

    for attempt in range(num_providers):
        idx = (start_idx + attempt) % num_providers
        name, model = PROVIDERS[idx]
        try:
            # bind_tools() attaches the tool schemas — same call for every provider
            bound = model.bind_tools(tools) if tools else model
            response = bound.invoke(messages)
            
            # If we succeeded on a provider other than the initial preferred one, update the preferred provider
            if idx != start_idx:
                with _provider_index_lock:
                    _preferred_provider_index = idx
                print(f"[llm_fallback] Switched preferred LLM provider to {name}")
                
            return response
        except Exception as exc:
            print(f"[llm_fallback] {name} failed: {exc}")
            last_error = exc

    raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

