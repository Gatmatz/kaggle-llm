import pytest

from kaggle_llm import _kaggle, config


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """No real Kaggle account, environment settings or state from this machine."""
    for var in config.ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("KAGGLE_LLM_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(_kaggle, "username", lambda: "me")
    monkeypatch.setattr(config, "_configured", {})
