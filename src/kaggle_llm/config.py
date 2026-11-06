"""Settings.

Priority: arguments to a call > `configure()` > environment variables > defaults.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from pathlib import Path

from kaggle_llm.errors import ConfigError


@dataclass(frozen=True)
class Settings:
    """All settings. Usually built for you by `configure()` and `get_settings()`."""

    ngrok_authtoken: str | None = None
    """ngrok authtoken (required to start a server)."""
    ngrok_domain: str | None = None
    """Static ngrok domain. Without it the URL changes on every start."""
    kaggle_api_token: str | None = None
    """Kaggle API token, if Kaggle credentials are not configured on this machine."""
    notebook_slug: str = "kaggle-llm-server"
    """Name of the notebook in your Kaggle account (the username is detected from your credentials)."""
    accelerator: str = "NvidiaTeslaT4"
    model: str = "qwen3.5:9b"
    context_length: int = 32768
    num_parallel: int = 1
    keep_alive: str = "30m"
    idle_minutes: int = 20
    max_hours: float = 4.0
    wait_minutes: int = 20
    state_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.ngrok_domain:
            domain = self.ngrok_domain.removeprefix("https://").removeprefix("http://").strip("/ ")
            object.__setattr__(self, "ngrok_domain", domain or None)
        if self.state_dir is not None:
            object.__setattr__(self, "state_dir", Path(self.state_dir).expanduser())

    @property
    def static_url(self) -> str | None:
        return f"https://{self.ngrok_domain}" if self.ngrok_domain else None

    def replace(self, **changes) -> Settings:
        """A copy with the given values changed (None values are ignored)."""
        return dataclasses.replace(self, **{k: v for k, v in changes.items() if v is not None})


ENV_VARS = {
    "ngrok_authtoken": "NGROK_AUTHTOKEN",
    "ngrok_domain": "NGROK_DOMAIN",
    "kaggle_api_token": "KAGGLE_API_TOKEN",
    "notebook_slug": "KAGGLE_LLM_NOTEBOOK_SLUG",
    "accelerator": "KAGGLE_LLM_ACCELERATOR",
    "model": "KAGGLE_LLM_MODEL",
    "context_length": "KAGGLE_LLM_CONTEXT_LENGTH",
    "num_parallel": "KAGGLE_LLM_NUM_PARALLEL",
    "keep_alive": "KAGGLE_LLM_KEEP_ALIVE",
    "idle_minutes": "KAGGLE_LLM_IDLE_MINUTES",
    "max_hours": "KAGGLE_LLM_MAX_HOURS",
    "wait_minutes": "KAGGLE_LLM_WAIT_MINUTES",
    "state_dir": "KAGGLE_LLM_STATE_DIR",
}
_FIELDS = {f.name for f in dataclasses.fields(Settings)}
_INTS = {"context_length", "num_parallel", "idle_minutes", "wait_minutes"}
_FLOATS = {"max_hours"}

_configured: dict = {}


def _parse(name: str, raw: str):
    try:
        if name in _INTS:
            return int(raw)
        if name in _FLOATS:
            return float(raw)
    except ValueError:
        raise ConfigError(f"{ENV_VARS[name]}={raw!r} is not a number.") from None
    return raw


def _check(values: dict) -> None:
    unknown = set(values) - _FIELDS
    if unknown:
        raise TypeError(f"Unknown setting(s): {', '.join(sorted(unknown))}")


def configure(**settings) -> Settings:
    """Set defaults for this process, e.g. `configure(ngrok_authtoken="...", model="qwen3:14b")`.

    Later calls update earlier ones; pass a value of None to unset it.
    """
    _check(settings)
    for name, value in settings.items():
        if value is None:
            _configured.pop(name, None)
        else:
            _configured[name] = value
    return get_settings()


def get_settings(**overrides) -> Settings:
    """The settings in effect, with `overrides` applied on top."""
    _check(overrides)
    values = {name: _parse(name, os.environ[var]) for name, var in ENV_VARS.items() if os.environ.get(var)}
    values.update(_configured)
    values.update({k: v for k, v in overrides.items() if v is not None})
    return Settings(**values)
