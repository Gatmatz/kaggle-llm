"""Builds the Kaggle notebook from `remote/server.py` and the settings."""

from __future__ import annotations

import json
import os
from importlib.resources import files
from pathlib import Path
from pprint import pformat

from kaggle_llm.config import Settings

INSTALL = """\
import subprocess
subprocess.run("sudo apt-get install -y -qq zstd", shell=True, check=True)  # needed by the Ollama installer
subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
subprocess.run("pip install -q 'pyngrok>=9,<10' 'aiohttp>=3.9'", shell=True, check=True)
"""


def parameters(settings: Settings, *, include_token: bool, shutdown_token: str = "") -> dict:
    return {
        "MODEL": settings.model,
        "CONTEXT_LENGTH": settings.context_length,
        "NUM_PARALLEL": settings.num_parallel,
        "KEEP_ALIVE": settings.keep_alive,
        "IDLE_MINUTES": settings.idle_minutes,
        "MAX_HOURS": settings.max_hours,
        "NGROK_DOMAIN": settings.ngrok_domain or "",
        "NGROK_AUTHTOKEN": (settings.ngrok_authtoken or "") if include_token else "",
        "SHUTDOWN_TOKEN": shutdown_token,
    }


def build(params: dict) -> dict:
    server = files("kaggle_llm.remote").joinpath("server.py").read_text(encoding="utf-8")
    cells = [
        "# Parameters, written by `kaggle-llm start`\nPARAMS = " + pformat(params, sort_dicts=False),
        INSTALL,
        server,
        "main(PARAMS)",
    ]
    return {
        "cells": [{"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                   "source": source.splitlines(keepends=True)} for source in cells],
        "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write(path: str | os.PathLike, settings: Settings, *, include_token: bool = False) -> Path:
    """Write the notebook to run it by hand on kaggle.com.

    Without `include_token`, it reads the ngrok token from the Kaggle secret NGROK_AUTHTOKEN.
    """
    path = Path(path)
    path.write_text(json.dumps(build(parameters(settings, include_token=include_token)), indent=1))
    return path
