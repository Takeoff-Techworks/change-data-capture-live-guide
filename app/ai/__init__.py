"""Read-only assistant providers."""

from app.config import settings

from .deterministic import DeterministicAssistantProvider


def assistant_provider():
    name = settings.assistant_provider.lower()
    if name == "deterministic":
        return DeterministicAssistantProvider()
    if name in {"gemini", "openai"}:
        from .llm import LLMAssistantProvider

        return LLMAssistantProvider(name)
    raise RuntimeError(
        f"Unsupported ASSISTANT_PROVIDER '{settings.assistant_provider}'. Use deterministic, gemini, or openai."
    )
