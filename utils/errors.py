"""Custom exception hierarchy for the Autonomous AI Creator."""


class AgentError(Exception):
    """Base exception for all agent subsystem errors."""
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigConflictError(AgentError):
    """Raised when an active agent configuration already exists and cannot be overwritten."""
    pass


class DiscoveryError(AgentError):
    """Raised when news fetching, scraping, or parsing encounters an unrecoverable failure."""
    pass


class EditorialError(AgentError):
    """Raised during editorial scoring, evaluation, or rationale generation."""
    pass


class GenerationError(AgentError):
    """Raised when LLM synthesis fails or produces output that violates style guardrails."""
    pass


class RateLimitError(AgentError):
    """Raised when daily post cap is exceeded or upstream API quota is hit."""
    pass
