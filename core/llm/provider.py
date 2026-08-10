"""Pluggable LLM provider with structured output support.

Never send the full repository. Callers must pass only:
diff + relevant symbols + context snippets.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredLLMResult(BaseModel):
    """Wrapper for structured LLM responses with metadata."""

    data: dict[str, Any] = Field(default_factory=dict)
    raw_text: str = ""
    model: str = ""
    provider: str = ""
    tokens_used: int | None = None
    success: bool = True
    error: str | None = None


class LLMProvider(ABC):
    """Abstract LLM interface used by agents."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        ...

    def structured(
        self,
        system: str,
        user: str,
        schema: type[BaseModel],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> StructuredLLMResult:
        """Request JSON matching a Pydantic schema. Falls back to parse."""
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        prompt = (
            f"{user}\n\n"
            "Respond with ONLY valid JSON matching this schema. "
            "No markdown fences, no commentary.\n\n"
            f"SCHEMA:\n{schema_json}"
        )
        try:
            text = self.complete(system, prompt, temperature=temperature, max_tokens=max_tokens)
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [ln for ln in lines if not ln.strip().startswith("```")]
                cleaned = "\n".join(lines)
            data = json.loads(cleaned)
            # Validate
            schema.model_validate(data)
            return StructuredLLMResult(
                data=data,
                raw_text=text,
                model=getattr(self, "model", ""),
                provider=getattr(self, "name", "unknown"),
                success=True,
            )
        except Exception as e:
            logger.warning("Structured LLM call failed: %s", e)
            return StructuredLLMResult(
                success=False,
                error=str(e),
                raw_text=locals().get("text", ""),
                model=getattr(self, "model", ""),
                provider=getattr(self, "name", "unknown"),
            )


class NullLLMProvider(LLMProvider):
    """No-op provider when no API key is configured."""

    name = "null"
    model = "none"

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        raise RuntimeError("No LLM provider configured. Set OPENAI_API_KEY or qgate llm.provider.")


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

    def complete(self, system: str, user: str, *, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
        except ImportError as e:
            raise RuntimeError("langchain-openai not installed") from e

        llm = ChatOpenAI(
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=self.api_key,
        )
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(resp.content)


def get_llm_provider(config: dict[str, Any] | None = None) -> LLMProvider:
    """Factory: returns a real provider if credentials exist, else NullLLMProvider."""
    config = config or {}
    llm_cfg = config.get("llm") or {}
    if isinstance(llm_cfg, dict):
        provider = (llm_cfg.get("provider") or "openai").lower()
        model = llm_cfg.get("model") or "gpt-4o-mini"
    else:
        provider = "openai"
        model = "gpt-4o-mini"

    if provider == "openai" and os.environ.get("OPENAI_API_KEY"):
        try:
            return OpenAILLMProvider(model=model)
        except Exception as e:
            logger.warning("OpenAI provider unavailable: %s", e)

    # Future: anthropic, azure, ollama
    logger.info("Using NullLLMProvider (no API key / provider unavailable)")
    return NullLLMProvider()
