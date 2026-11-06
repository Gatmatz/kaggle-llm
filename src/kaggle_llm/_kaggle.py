"""Thin wrapper around the official `kaggle` package."""

from __future__ import annotations

import functools
import json
import os
import re
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import requests

from kaggle_llm.errors import KaggleError, QuotaExceededError

CODE_FILE = "kaggle_llm_server.ipynb"


@dataclass(frozen=True)
class PushResult:
    notebook: str
    version: int | None
    url: str


def use_token(token: str | None) -> None:
    """Make an explicitly configured token win over the machine's Kaggle credentials."""
    if token and os.environ.get("KAGGLE_API_TOKEN") != token:
        os.environ["KAGGLE_API_TOKEN"] = token
        username.cache_clear()


def api():
    from kaggle.api.kaggle_api_extended import KaggleApi  # importing `kaggle` authenticates, so import late

    kaggle = KaggleApi()
    try:
        kaggle.authenticate()
    except (Exception, SystemExit) as e:  # the package calls exit() when credentials are missing
        raise KaggleError(
            "No Kaggle credentials found. Run `kaggle auth login`, or pass kaggle_api_token."
        ) from e
    return kaggle


@functools.cache
def username() -> str:
    name = api().get_config_value("username")
    if not name:
        raise KaggleError("Could not determine your Kaggle username; set the notebook explicitly.")
    return name


def find_notebook(kaggle, notebook_id: str) -> dict | None:
    """Look the notebook up by id, then by title (Kaggle derives the slug from the title)."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            kaggle.kernels_pull(notebook_id, tmp, metadata=True, quiet=True)
            meta = json.loads((Path(tmp) / "kernel-metadata.json").read_text())
            return {"id": meta["id"], "id_no": meta.get("id_no"), "title": meta["title"]}
        except Exception:  # noqa: BLE001, S110 - not found by id
            pass
    slug = notebook_id.partition("/")[2].lower()
    for kernel in kaggle.kernels_list(mine=True, search=slug.replace("-", " "), page_size=50) or []:
        title_slug = re.sub(r"[^a-z0-9]+", "-", kernel.title.lower()).strip("-")
        if title_slug == slug or kernel.ref.lower().endswith("/" + slug):
            return {"id": kernel.ref, "id_no": kernel.id, "title": kernel.title}
    return None


def _push_error(code: int | None, reason: str) -> KaggleError:
    if "quota" in reason.lower():
        return QuotaExceededError(f"The weekly Kaggle GPU quota is used up. Kaggle says: {reason}")
    if code in (401, 403):
        return KaggleError(f"Kaggle rejected the credentials (HTTP {code}): {reason}")
    if code == 409:
        return KaggleError(
            f"Kaggle refused a new notebook version (HTTP 409): {reason}\n"
            "The notebook is probably running (an earlier start, or an open editor on kaggle.com). "
            "Run `kaggle-llm stop` or stop it on kaggle.com, then retry."
        )
    return KaggleError(f"Pushing the notebook failed (HTTP {code}): {reason}")


def push(notebook_id: str, nb: dict, *, accelerator: str, timeout_s: int) -> PushResult:
    """Save `nb` as a new version of the private notebook and run it."""
    kaggle = api()
    existing = find_notebook(kaggle, notebook_id)
    existing = existing or {"id": notebook_id, "id_no": None, "title": notebook_id.partition("/")[2]}
    metadata = {
        **existing,  # same id and title, otherwise Kaggle tries to create a second notebook
        "code_file": CODE_FILE,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,  # always: the notebook contains the ngrok token
        "enable_gpu": True,
        "enable_internet": True,
    }
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / CODE_FILE).write_text(json.dumps(nb))
        (Path(tmp) / "kernel-metadata.json").write_text(json.dumps(metadata))
        try:
            response = kaggle.kernels_push(tmp, timeout=str(timeout_s), acc=accelerator)
        except requests.HTTPError as e:
            raise _push_error(e.response.status_code, e.response.text.strip()) from e
    if getattr(response, "error", ""):
        raise _push_error(None, response.error)
    return PushResult(existing["id"], getattr(response, "version_number", None) or None,
                      getattr(response, "url", ""))


def status(kernel: str) -> tuple[str, str]:
    """(status, failure message), e.g. ("running", "")."""
    try:
        response = api().kernels_status(kernel)
    except KaggleError:
        raise
    except Exception as e:
        raise KaggleError(f"Could not read the status of {kernel}: {e}") from e
    state = getattr(response.status, "name", str(response.status))
    return state.lower(), response.failure_message or ""


def log_lines(kernel: str) -> Iterator[str]:
    """The notebook's live log, one string per event."""
    for event in api().kernels_logs_stream(kernel):
        yield str(event.get("data", ""))
