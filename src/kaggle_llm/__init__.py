"""Run an Ollama LLM on a free Kaggle GPU and use it from your code."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from kaggle_llm.config import Settings, configure, get_settings
from kaggle_llm.errors import (
    ConfigError,
    KaggleError,
    KaggleLLMError,
    QuotaExceededError,
    ServerNotReadyError,
)
from kaggle_llm.lifecycle import NGROK_HEADERS, Server, Status, connect, start, status, stop, url

__version__ = "0.1.0"

__all__ = [
    "NGROK_HEADERS",
    "ConfigError",
    "KaggleError",
    "KaggleLLMError",
    "QuotaExceededError",
    "Server",
    "ServerNotReadyError",
    "Settings",
    "Status",
    "configure",
    "connect",
    "get_settings",
    "session",
    "start",
    "status",
    "stop",
    "url",
]


@contextmanager
def session(settings: Settings | None = None, *, stop_on_exit: bool = True, **kwargs) -> Iterator[Server]:
    """Start (or reuse) the server for the duration of a `with` block."""
    server = start(settings, **kwargs)
    try:
        yield server
    finally:
        if stop_on_exit:
            server.stop()
