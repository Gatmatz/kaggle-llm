"""The notebook's proxy (remote/server.py) against a fake Ollama, and the local lifecycle against the proxy."""

import asyncio
import json
import socket
import threading
import time

import pytest
import requests
from aiohttp import web

import kaggle_llm
from kaggle_llm import lifecycle
from kaggle_llm.config import Settings
from kaggle_llm.remote import server as remote


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_ollama():
    """A fake Ollama that records Host headers and streams 3 slow chunks on /api/chat."""
    port, hosts, loop = free_port(), [], asyncio.new_event_loop()

    async def chat(request):
        hosts.append(request.headers.get("Host"))
        body = await request.json()
        resp = web.StreamResponse(headers={"Content-Type": "application/x-ndjson"})
        await resp.prepare(request)
        for i in range(3):
            await resp.write(json.dumps({"model": body["model"], "i": i}).encode() + b"\n")
            await asyncio.sleep(0.4)
        await resp.write_eof()
        return resp

    async def tags(request):
        hosts.append(request.headers.get("Host"))
        return web.json_response({"models": [{"name": "m:latest"}]})

    app = web.Application()
    app.router.add_post("/api/chat", chat)
    app.router.add_get("/api/tags", tags)
    runner = web.AppRunner(app)

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", port).start())
        loop.run_forever()

    threading.Thread(target=run, daemon=True).start()
    time.sleep(0.3)
    yield port, hosts
    asyncio.run_coroutine_threadsafe(runner.cleanup(), loop).result(5)
    loop.call_soon_threadsafe(loop.stop)


@pytest.fixture
def proxy(fake_ollama, monkeypatch):
    ollama_port, hosts = fake_ollama
    monkeypatch.setattr(remote, "OLLAMA_PORT", ollama_port)
    monkeypatch.setattr(remote, "PROXY_PORT", free_port())
    params = {"MODEL": "m", "CONTEXT_LENGTH": 32768, "NUM_PARALLEL": 1, "KEEP_ALIVE": "30m",
              "IDLE_MINUTES": 20, "MAX_HOURS": 4, "NGROK_DOMAIN": "", "NGROK_AUTHTOKEN": "",
              "SHUTDOWN_TOKEN": "tok"}
    state = remote.State(params)
    close = remote.start_proxy(state)
    time.sleep(0.3)
    yield f"http://127.0.0.1:{remote.PROXY_PORT}", state, hosts
    close()


def test_not_ready_then_streaming_and_in_flight(proxy):
    url, state, hosts = proxy
    assert requests.get(url + "/api/tags").status_code == 503  # still pulling
    assert lifecycle.fetch_info(url)["phase"] == "starting"
    state.phase = "ready"

    seen_during = {}

    def watch():
        time.sleep(0.5)
        seen_during.update(lifecycle.fetch_info(url))

    t = threading.Thread(target=watch)
    t.start()
    start = time.time()
    with requests.post(url + "/api/chat", json={"model": "m"}, stream=True) as r:
        arrivals = [(json.loads(line)["i"], time.time() - start) for line in r.iter_lines() if line]
    t.join()
    assert [i for i, _ in arrivals] == [0, 1, 2]
    assert arrivals[0][1] < 0.3, "the first chunk must arrive before the stream ends (no buffering)"
    assert seen_during["in_flight"] == 1 and seen_during["idle_s"] == 0
    assert all(h.startswith("127.0.0.1") for h in hosts), hosts  # local Host header for Ollama
    info = lifecycle.fetch_info(url)
    assert info["in_flight"] == 0 and info["requests"] == 1 and info["context_length"] == 32768


def test_shutdown_needs_the_token(proxy, tmp_path):
    url, state, _ = proxy
    assert requests.post(url + "/_kaggle_llm/shutdown", headers={"X-Kaggle-LLM-Token": "no"}).status_code == 403
    assert not state.stop.is_set()

    s = Settings(state_dir=tmp_path)
    lifecycle._save_state(s, url=url, shutdown_token="tok", notebook="me/kaggle-llm-server", version=3)
    assert kaggle_llm.stop(s, quiet=True) is True
    assert state.stop.is_set()
    assert not lifecycle._state_file(s).exists()


def test_start_reuses_a_ready_server(proxy, tmp_path, monkeypatch):
    url, state, _ = proxy
    state.phase = "ready"
    s = Settings(ngrok_authtoken="t", model="m", state_dir=tmp_path)
    lifecycle._save_state(s, url=url, shutdown_token="tok", notebook="me/kaggle-llm-server", version=3)

    def no_push(*a, **k):
        raise AssertionError("must not push when a matching server is ready")

    monkeypatch.setattr(lifecycle._kaggle, "push", no_push)
    server = kaggle_llm.start(s, quiet=True)
    assert server.url == url and server.version == 3
    assert server.openai_base_url == url + "/v1"
    assert kaggle_llm.connect(s).model == "m"

    monkeypatch.setattr(lifecycle._kaggle, "status", lambda kernel: ("running", ""))
    st = kaggle_llm.status(s)
    assert st.ready and st.notebook == "me/kaggle-llm-server/3" and st.kaggle_status == "running"


def test_start_pushes_and_waits(proxy, tmp_path, monkeypatch):
    """No static domain: the URL comes from the notebook log, then the server becomes ready."""
    url, state, _ = proxy
    s = Settings(ngrok_authtoken="t", model="m", state_dir=tmp_path, wait_minutes=1)
    pushed = {}

    def fake_push(notebook_id, nb, *, accelerator, timeout_s):
        pushed["params"] = "".join(nb["cells"][0]["source"])
        threading.Timer(1.0, lambda: setattr(state, "phase", "ready")).start()
        return lifecycle._kaggle.PushResult(notebook=notebook_id, version=7, url="https://kaggle/x")

    monkeypatch.setattr(lifecycle._kaggle, "push", fake_push)
    monkeypatch.setattr(lifecycle._kaggle, "status", lambda kernel: ("running", ""))
    monkeypatch.setattr(lifecycle._kaggle, "log_lines", lambda kernel: iter(["boot", f"KAGGLE_LLM_URL={url}"]))
    monkeypatch.setattr(lifecycle, "_URL_IN_LOG", __import__("re").compile(r"KAGGLE_LLM_URL=(\S+)"))
    server = kaggle_llm.start(s, quiet=True)
    assert server.url == url and server.version == 7
    assert "'CONTEXT_LENGTH': 32768" in pushed["params"]
    saved = lifecycle._load_state(s)
    assert saved["url"] == url and saved["shutdown_token"] in pushed["params"]
