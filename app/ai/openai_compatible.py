from app.ai.deterministic import DeterministicAssistantProvider


class OpenAICompatibleAssistantProvider(DeterministicAssistantProvider):
    """Explicit opt-in extension point; networking is intentionally not enabled by default."""
