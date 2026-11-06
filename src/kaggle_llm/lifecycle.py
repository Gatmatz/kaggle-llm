"""Start, find, inspect and stop the server on Kaggle."""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

from kaggle_llm import _kaggle, notebook
from kaggle_llm.config import Settings, get_settings
from kaggle_llm.errors import ConfigError, KaggleError, ServerNotReadyError

NGROK_HEADERS = {"ngrok-skip-browser-warning": "true"}
"""Headers that skip ngrok's browser warning page, for clients that look like a browser."""

_URL_IN_LOG = re.compile(r"KAGGLE_LLM_URL=(https://\S+)")
_RUNNING = ("starting", "pulling", "warming_up", "ready")


@dataclass(frozen=True)
class Server:
    """A running server. Create it with `start()` or `connect()`."""

    url: str
    model: str
    notebook: str
    version: int | None = None
    settings: Settings = field(default_factory=Settings, repr=False, compare=False)

    @property
    def openai_base_url(self) -> str:
        """Base URL of the OpenAI-compatible API (the native Ollama API is at `url`)."""
        return self.url + "/v1"

    def info(self) -> dict | None:
        return fetch_info(self.url)

    def is_ready(self) -> bool:
        return (self.info() or {}).get("phase") == "ready"

    def stop(self) -> bool:
        return stop(self.settings)


@dataclass(frozen=True)
class Status:
    notebook: str
    url: str | None
    kaggle_status: str | None
    """Kaggle's view: queued, running, complete, error... (None if unknown)."""
    info: dict | None
    """The server's /_kaggle_llm/info answer (None if unreachable)."""

    @property
    def phase(self) -> str | None:
        return self.info["phase"] if self.info else None

    @property
    def ready(self) -> bool:
        return self.phase == "ready"

    def __str__(self) -> str:
        return (f"notebook  {self.notebook}: {self.kaggle_status or 'unknown'}\n"
                f"server    {self.url or '-'}: {_describe(self.info)}")


# Local state: the URL and shutdown token of the last start, one file per notebook.

def _notebook_id(s: Settings) -> str:
    _kaggle.use_token(s.kaggle_api_token)
    return f"{_kaggle.username()}/{s.notebook_slug}"


def _state_file(s: Settings) -> Path:
    base = s.state_dir or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kaggle-llm"
    return base / (_notebook_id(s).replace("/", "__") + ".json")


def _load_state(s: Settings) -> dict:
    try:
        return json.loads(_state_file(s).read_text())
    except (OSError, ValueError):
        return {}


def _save_state(s: Settings, **values) -> dict:
    path = _state_file(s)
    state = {**_load_state(s), **values}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600)  # holds the shutdown token
    path.write_text(json.dumps(state, indent=2))
    return state


def _clear_state(s: Settings) -> None:
    _state_file(s).unlink(missing_ok=True)


def _known_url(s: Settings) -> str | None:
    return s.static_url or _load_state(s).get("url")


# Helpers

def fetch_info(url: str, timeout: float = 10) -> dict | None:
    """The server's info, or None if the tunnel is offline."""
    try:
        response = requests.get(url + "/_kaggle_llm/info", headers=NGROK_HEADERS, timeout=timeout)
        info = response.json() if response.ok else None
    except (requests.RequestException, ValueError):
        return None
    return info if isinstance(info, dict) and "phase" in info else None


def _describe(info: dict | None) -> str:
    if not info:
        return "offline"
    pull = info.get("pull") or {}
    if info["phase"] == "pulling" and pull.get("total"):
        return f"downloading {info['model']} ({100 * pull.get('completed', 0) // pull['total']}%)"
    if info["phase"] == "error":
        return f"error: {info.get('error')}"
    return info["phase"].replace("_", " ")


def _settings(settings: Settings | None, overrides: dict) -> Settings:
    return settings.replace(**overrides) if settings else get_settings(**overrides)


def _log(quiet: bool, message: str) -> None:
    if not quiet:
        print(message, file=sys.stderr, flush=True)


def _server(s: Settings, url: str) -> Server:
    state = _load_state(s)
    return Server(url, s.model, state.get("notebook") or _notebook_id(s), state.get("version"), s)


# Public API

def url(settings: Settings | None = None, **overrides) -> str:
    """The server URL: NGROK_DOMAIN, or the URL found by the last `start()`."""
    found = _known_url(_settings(settings, overrides))
    if not found:
        raise ServerNotReadyError("No server URL known. Run `kaggle-llm start` first.")
    return found


def connect(settings: Settings | None = None, *, require_ready: bool = True, **overrides) -> Server:
    """The server that is already running (started by the CLI or another process)."""
    s = _settings(settings, overrides)
    server_url = url(s)
    if require_ready:
        info = fetch_info(server_url)
        if (info or {}).get("phase") != "ready":
            raise ServerNotReadyError(f"The server at {server_url} is not ready ({_describe(info)}).")
        s = s.replace(model=info["model"])
    return _server(s, server_url)


def start(settings: Settings | None = None, *, wait: bool = True, restart: bool = False, quiet: bool = False,
          **overrides) -> Server:
    """Start the server on Kaggle, or reuse a running one with the same model and context length.

    Keyword overrides (e.g. `model="qwen3:14b"`) win over `configure()` and the environment. With `wait=False`
    it returns right after the notebook is pushed. Interrupting the wait does not stop the notebook.
    """
    s = _settings(settings, overrides)
    if not s.ngrok_authtoken:
        raise ConfigError("No ngrok authtoken. Pass ngrok_authtoken=... (or set NGROK_AUTHTOKEN). "
                          "Get it at https://dashboard.ngrok.com/get-started/your-authtoken")
    notebook_id = _notebook_id(s)

    current_url = _known_url(s)
    info = fetch_info(current_url) if current_url else None
    if info and info["phase"] in _RUNNING:
        running = (info["model"], info["context_length"], info["num_parallel"])
        if running == (s.model, s.context_length, s.num_parallel) and not restart:
            _log(quiet, f"Reusing the server at {current_url} ({_describe(info)}).")
            return _wait_until_ready(s, current_url, None, quiet) if wait else _server(s, current_url)
        _log(quiet, "Stopping the running server to start one with the new settings.")
        if not stop(s, quiet=True):
            raise ServerNotReadyError("A server with other settings is running and cannot be stopped from "
                                      "here. Stop it on kaggle.com and retry.")
        while fetch_info(current_url, timeout=5):
            time.sleep(5)

    shutdown_token = secrets.token_urlsafe(24)
    nb = notebook.build(notebook.parameters(s, include_token=True, shutdown_token=shutdown_token))
    _log(quiet, f"Pushing {notebook_id} ({s.model}, context {s.context_length}, {s.accelerator})...")
    pushed = _kaggle.push(notebook_id, nb, accelerator=s.accelerator, timeout_s=int(s.max_hours * 3600) + 900)
    _log(quiet, f"Version {pushed.version} started: {pushed.url}")
    _save_state(s, notebook=pushed.notebook, version=pushed.version, url=s.static_url,
                shutdown_token=shutdown_token)
    if not wait:
        return _server(s, s.static_url or "")
    kernel = f"{pushed.notebook}/{pushed.version}" if pushed.version else pushed.notebook
    return _wait_until_ready(s, s.static_url, kernel, quiet)


def _wait_until_ready(s: Settings, server_url: str | None, kernel: str | None, quiet: bool) -> Server:
    found_urls: list[str] = []
    done = threading.Event()

    def read_log():
        while not done.is_set():
            try:
                for line in _kaggle.log_lines(kernel):
                    found_urls.extend(_URL_IN_LOG.findall(line))
                    if done.is_set():
                        return
            except Exception:  # noqa: BLE001, S110 - the log is not available yet
                pass
            done.wait(10)

    if kernel and not server_url:
        threading.Thread(target=read_log, daemon=True).start()

    deadline = time.time() + s.wait_minutes * 60
    last_message, next_kaggle_check, kaggle_status = "", 0.0, "unknown"
    try:
        while time.time() < deadline:
            if found_urls and found_urls[-1] != server_url:
                server_url = found_urls[-1]
                _save_state(s, url=server_url)
                _log(quiet, f"Tunnel URL: {server_url}")

            info = fetch_info(server_url) if server_url else None
            if info and info["phase"] == "ready":
                _log(quiet, f"Ready at {server_url}. Stops after {info['idle_minutes']} idle minutes.")
                return _server(s, server_url)
            if info and info["phase"] == "error":
                raise KaggleError(f"The server failed on Kaggle: {info['error']}")

            if kernel and time.time() >= next_kaggle_check:
                next_kaggle_check = time.time() + 30
                try:
                    kaggle_status, failure = _kaggle.status(kernel)
                except KaggleError:
                    kaggle_status, failure = "unknown", ""
                if kaggle_status in ("complete", "error", "cancel_requested", "cancel_acknowledged"):
                    raise KaggleError(f"The notebook ended ({kaggle_status}) before the server was ready. "
                                      f"{failure} Log: kaggle kernels logs {kernel}")

            server = _describe(info) if server_url else "waiting for the URL"
            message = f"  kaggle: {kaggle_status}, server: {server}"
            if message != last_message:
                _log(quiet, message)
                last_message = message
            time.sleep(10)
    finally:
        done.set()
    raise ServerNotReadyError(f"Not ready after {s.wait_minutes} minutes. Check `kaggle-llm status`.")


def stop(settings: Settings | None = None, *, quiet: bool = False, **overrides) -> bool:
    """Stop the running server. Returns False if there is nothing this machine can stop."""
    s = _settings(settings, overrides)
    server_url, token = _known_url(s), _load_state(s).get("shutdown_token")
    if not server_url or not fetch_info(server_url):
        _log(quiet, "No server is reachable.")
        return False
    if not token:
        _log(quiet, "This server was not started from this machine. Stop it on kaggle.com.")
        return False
    response = requests.post(server_url + "/_kaggle_llm/shutdown", timeout=15,
                             headers={**NGROK_HEADERS, "X-Kaggle-LLM-Token": token})
    if not response.ok:
        _log(quiet, f"The server refused to stop: HTTP {response.status_code}.")
        return False
    _clear_state(s)
    _log(quiet, f"Stopping the server at {server_url}.")
    return True


def status(settings: Settings | None = None, **overrides) -> Status:
    """What Kaggle and the server report right now."""
    s = _settings(settings, overrides)
    state = _load_state(s)
    kernel = state.get("notebook") or _notebook_id(s)
    if state.get("version"):
        kernel += f"/{state['version']}"
    try:
        kaggle_status = _kaggle.status(kernel)[0]
    except KaggleError:
        kaggle_status = None
    server_url = _known_url(s)
    return Status(kernel, server_url, kaggle_status, fetch_info(server_url) if server_url else None)
