"""Anthropic API wrapper. Step 1: stub interface only. Step 8 plumbs real calls.

The interface is fixed now so callers can be written against it without churn.
"""

from .client import (
    LLMClient,
    StubLLMClient,
    get_llm_client,
    set_llm_client_for_tests,
)

__all__ = ["LLMClient", "StubLLMClient", "get_llm_client", "set_llm_client_for_tests"]
