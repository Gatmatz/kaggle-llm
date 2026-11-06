"""The server that runs inside the Kaggle notebook.

    internet -> ngrok -> proxy :8000 -> ollama :11434 (localhost only)

The proxy forwards everything to Ollama and adds two endpoints:
    GET  /_kaggle_llm/info      phase, model, download progress, activity
    POST /_kaggle_llm/shutdown  stops the notebook (needs the run's token)
It also counts requests in flight, so the idle timer never fires during a long generation.

This file is pasted into the notebook as is: it may only import the standard library,
aiohttp and pyngrok.
"""

import asyncio
import json
import os
import secrets
import subprocess
import threading
import time
import urllib.request

OLLAMA_PORT = 11434
PROXY_PORT = 8000
SKIP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "upgrade", "host", "content-length"}


class State:
    def __init__(self, params):
        self.params = params
        self.phase = "starting"  # starting, pulling, warming_up, ready, error, stopping
        self.error = None
        self.pull = {}
        self.started = self.last_activity = time.time()
        self.in_flight = self.requests = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def info(self):
        p = self.params
        with self.lock:
            idle = 0 if self.in_flight else time.time() - self.last_activity
            return {
                "phase": self.phase, "error": self.error, "model": p["MODEL"],
                "context_length": p["CONTEXT_LENGTH"], "num_parallel": p["NUM_PARALLEL"],
                "idle_minutes": p["IDLE_MINUTES"], "uptime_s": round(time.time() - self.started),
                "idle_s": round(idle), "in_flight": self.in_flight, "requests": self.requests,
                "pull": self.pull,
            }


def ollama_request(path, payload=None, timeout=10):
    request = urllib.request.Request(
        f"http://127.0.0.1:{OLLAMA_PORT}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(request, timeout=timeout)


def start_ollama(params):
    env = dict(
        os.environ,
        OLLAMA_HOST=f"127.0.0.1:{OLLAMA_PORT}",
        OLLAMA_CONTEXT_LENGTH=str(params["CONTEXT_LENGTH"]),
        OLLAMA_NUM_PARALLEL=str(params["NUM_PARALLEL"]),
        OLLAMA_KEEP_ALIVE=str(params["KEEP_ALIVE"]),
    )
    process = subprocess.Popen(["ollama", "serve"], env=env, stdout=open("ollama.log", "w"),
                               stderr=subprocess.STDOUT)
    for _ in range(120):
        try:
            ollama_request("/api/version").close()
            return process
        except OSError:
            if process.poll() is not None:
                break
            time.sleep(1)
    raise RuntimeError("Ollama did not start, see ollama.log")


def pull_model(state):
    model = state.params["MODEL"]
    with ollama_request("/api/pull", {"model": model, "stream": True}, timeout=3600) as response:
        for line in filter(bytes.strip, response):
            event = json.loads(line)
            if "error" in event:
                raise RuntimeError(f"Pulling {model} failed: {event['error']}")
            with state.lock:
                state.pull = {k: event[k] for k in ("status", "completed", "total") if k in event}


def warm_up(model):
    try:
        ollama_request("/api/generate", {"model": model, "prompt": "Hi", "stream": False}, timeout=900).close()
    except OSError as e:
        print(f"Warm-up failed, the first request will be slower: {e}")


def start_proxy(state):
    """Run the proxy on its own event loop in a thread (the notebook kernel already runs one)."""
    from aiohttp import ClientSession, ClientTimeout, web

    upstream = f"http://127.0.0.1:{OLLAMA_PORT}"
    session_key = web.AppKey("session", ClientSession)

    async def handle(request):
        if request.path == "/_kaggle_llm/info":
            return web.json_response(state.info())
        if request.path == "/_kaggle_llm/shutdown" and request.method == "POST":
            token = request.headers.get("X-Kaggle-LLM-Token", "")
            if not secrets.compare_digest(token, state.params["SHUTDOWN_TOKEN"]):
                return web.json_response({"error": "invalid token"}, status=403)
            state.stop.set()
            return web.json_response({"stopping": True})
        if state.phase != "ready":
            return web.json_response({"error": f"server not ready ({state.phase})"}, status=503)

        with state.lock:
            state.in_flight += 1
            state.requests += 1
        try:
            headers = {k: v for k, v in request.headers.items() if k.lower() not in SKIP_HEADERS}
            async with request.app[session_key].request(
                request.method, upstream + request.path_qs, headers=headers, data=await request.read()
            ) as upstream_response:
                response = web.StreamResponse(status=upstream_response.status, headers={
                    k: v for k, v in upstream_response.headers.items() if k.lower() not in SKIP_HEADERS})
                await response.prepare(request)
                async for chunk in upstream_response.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
        finally:
            with state.lock:
                state.in_flight -= 1
                state.last_activity = time.time()

    async def open_session(app):
        app[session_key] = ClientSession(timeout=ClientTimeout(total=None), auto_decompress=False)

    async def close_session(app):
        await app[session_key].close()

    app = web.Application(client_max_size=1024**3)
    app.on_startup.append(open_session)
    app.on_cleanup.append(close_session)
    app.router.add_route("*", "/{path:.*}", handle)
    runner = web.AppRunner(app, access_log=None)
    loop = asyncio.new_event_loop()

    def serve():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, "127.0.0.1", PROXY_PORT).start())
        loop.run_forever()

    threading.Thread(target=serve, daemon=True).start()

    def close():
        asyncio.run_coroutine_threadsafe(runner.cleanup(), loop).result(timeout=10)
        loop.call_soon_threadsafe(loop.stop)

    return close


def open_tunnel(params):
    from pyngrok import conf, ngrok

    token = params["NGROK_AUTHTOKEN"]
    if not token:  # notebook run by hand: use the Kaggle secret
        from kaggle_secrets import UserSecretsClient
        token = UserSecretsClient().get_secret("NGROK_AUTHTOKEN")
    # Config version 2 uses the classic tunnels API, which accepts the `domain` option.
    config = conf.PyngrokConfig(config_version="2", config_path=os.path.abspath("ngrok.yml"), auth_token=token)
    ngrok.kill()
    options = {"domain": params["NGROK_DOMAIN"]} if params["NGROK_DOMAIN"] else {}
    tunnel = ngrok.connect(PROXY_PORT, pyngrok_config=config, **options)
    return tunnel.public_url.replace("http://", "https://", 1), lambda: ngrok.kill(pyngrok_config=config)


def wait_until_done(state):
    idle_limit = state.params["IDLE_MINUTES"] * 60
    uptime_limit = state.params["MAX_HOURS"] * 3600
    while not state.stop.wait(15):
        info = state.info()
        if info["idle_s"] >= idle_limit:
            return "idle timeout"
        if info["uptime_s"] >= uptime_limit:
            return "max hours reached"
    return "shutdown requested"


def main(params):
    params = {**params, "SHUTDOWN_TOKEN": params.get("SHUTDOWN_TOKEN") or secrets.token_urlsafe(24)}
    state = State(params)
    cleanups = []
    try:
        cleanups.append(start_ollama(params).terminate)
        cleanups.append(start_proxy(state))
        url, close_tunnel = open_tunnel(params)
        cleanups.append(close_tunnel)
        print(f"KAGGLE_LLM_URL={url}", flush=True)  # read from the log by `kaggle-llm start`

        state.phase = "pulling"
        pull_model(state)
        state.phase = "warming_up"
        warm_up(params["MODEL"])
        with state.lock:
            state.phase = "ready"
            state.last_activity = time.time()
        print(f"Ready: {params['MODEL']} at {url}", flush=True)
        print(f"Stopping: {wait_until_done(state)}", flush=True)
    except Exception as e:
        state.error, state.phase = f"{type(e).__name__}: {e}", "error"
        print(f"Error: {state.error}", flush=True)
        time.sleep(30)  # keep the tunnel open so the client can read the error
        raise
    finally:
        state.phase = "stopping"
        time.sleep(1)
        for cleanup in reversed(cleanups):
            try:
                cleanup()
            except Exception as e:
                print(f"Cleanup failed: {e}")
