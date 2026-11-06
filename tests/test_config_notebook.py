import ast
import json

import pytest

from kaggle_llm import notebook
from kaggle_llm.config import Settings, configure, get_settings
from kaggle_llm.errors import ConfigError


def test_priority_arguments_configure_environment(monkeypatch):
    monkeypatch.setenv("KAGGLE_LLM_MODEL", "from-env")
    monkeypatch.setenv("KAGGLE_LLM_CONTEXT_LENGTH", "16384")
    monkeypatch.setenv("NGROK_DOMAIN", "https://x.ngrok-free.app/")
    assert get_settings().model == "from-env"
    assert get_settings().context_length == 16384  # parsed
    assert get_settings().static_url == "https://x.ngrok-free.app"

    configure(model="configured")
    assert get_settings().model == "configured"  # configure() wins over the environment
    assert get_settings(model="argument").model == "argument"  # arguments win over everything

    configure(model=None)  # unset
    assert get_settings().model == "from-env"


def test_defaults_and_validation(monkeypatch):
    s = get_settings()
    assert (s.model, s.context_length, s.notebook_slug) == ("qwen3.5:9b", 32768, "kaggle-llm-server")
    with pytest.raises(TypeError):
        configure(bogus=1)
    with pytest.raises(TypeError):
        get_settings(bogus=1)
    monkeypatch.setenv("KAGGLE_LLM_CONTEXT_LENGTH", "lots")
    with pytest.raises(ConfigError):
        get_settings()


def test_notebook_parameters_are_valid_python():
    tricky = 'to"k\\en\'\n$1'
    s = Settings(ngrok_authtoken=tricky, ngrok_domain="d.ngrok-free.app",
                 context_length=65536)
    nb = notebook.build(notebook.parameters(s, include_token=True, shutdown_token="abc"))
    json.dumps(nb)
    code = [("".join(c["source"])) for c in nb["cells"] if c["cell_type"] == "code"]
    params_cell = code[0]
    ns: dict = {}
    exec(params_cell, ns)
    assert ns["PARAMS"]["NGROK_AUTHTOKEN"] == tricky
    assert ns["PARAMS"]["CONTEXT_LENGTH"] == 65536
    assert ns["PARAMS"]["NGROK_DOMAIN"] == "d.ngrok-free.app"
    for source in code:
        ast.parse(source)  # every cell is valid Python


def test_hand_run_notebook_has_no_token(tmp_path):
    s = Settings(ngrok_authtoken="tok-9f8e7d")
    path = notebook.write(tmp_path / "nb.ipynb", s)
    assert "tok-9f8e7d" not in path.read_text()
