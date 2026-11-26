"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class LLMProvider(ABC):
    """Interface for LLM providers — swap Ollama/OpenAI/Gemini freely."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens."""
        ...

    async def generate_with_tools(
        self,
        contents: Any,
        config: Any,
        model: str | None = None,
    ) -> Any:
        """Generate a structured response supporting function calls and usage_metadata."""
        raise NotImplementedError("generate_with_tools is not implemented on this provider")

    async def stream_with_tools(
        self,
        contents: Any,
        config: Any,
        model: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """Stream ('text', delta) and ('done', response) events with usage_metadata."""
        raise NotImplementedError("stream_with_tools is not implemented on this provider")
        yield  # pragma: no cover
