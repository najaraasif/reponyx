"""Provider-independent error types."""


class LLMProviderError(RuntimeError):
    """Raised for bounded provider, parsing, or budget failures."""
