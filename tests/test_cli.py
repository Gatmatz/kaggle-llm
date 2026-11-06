from kaggle_llm.cli import main


def test_notebook_command_has_no_token(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NGROK_AUTHTOKEN", "tok-123")
    assert main(["notebook", "nb.ipynb"]) == 0
    assert "tok-123" not in (tmp_path / "nb.ipynb").read_text()


def test_errors_are_reported_not_raised(capsys):
    assert main(["start"]) == 1
    assert "ngrok authtoken" in capsys.readouterr().err
