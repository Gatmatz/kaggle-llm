class KaggleLLMError(RuntimeError):
    """Base class for all kaggle-llm errors."""


class ConfigError(KaggleLLMError):
    """A setting is missing or invalid."""


class KaggleError(KaggleLLMError):
    """Kaggle refused a request, or the notebook failed."""


class QuotaExceededError(KaggleError):
    """The weekly Kaggle GPU quota is used up."""


class ServerNotReadyError(KaggleLLMError):
    """The server is not running, or did not become ready in time."""
