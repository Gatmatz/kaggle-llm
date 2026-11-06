# How it works

```
your code ──HTTPS──▶ ngrok ──▶ proxy :8000 ──▶ Ollama :11434
                              └────────── private Kaggle notebook (GPU) ──────────┘
```

1. `start()` writes your settings into a notebook and pushes it to Kaggle as a private notebook with GPU
   and internet enabled, using the Kaggle API.
2. The notebook installs Ollama, opens the ngrok tunnel, downloads the model and loads it into GPU memory.
3. `start()` finds the tunnel URL (your static ngrok domain, or the notebook's live log), waits until the
   model is ready, and returns a `Server`.
4. Your code sends requests to the tunnel URL. Your tools, memory and agent loop run on your machine; the
   Kaggle GPU only generates the model's replies.

## The proxy

Ollama only listens on `localhost` inside the notebook. A small proxy in front of it:

- forwards every request to Ollama, streaming included;
- counts requests in flight, so the idle timer never stops the notebook in the middle of a long generation;
- answers `GET /_kaggle_llm/info` with the server's phase, model and download progress;
- stops the notebook on `POST /_kaggle_llm/shutdown`, which requires a token created for each run and
  kept on the machine that started it.

The notebook stops itself after `idle_minutes` without requests, after `max_hours`, or when `stop()` is
called. The Kaggle API cannot stop a running notebook, which is why the proxy provides this.

## State

The URL and stop token of the running server are kept in `~/.cache/kaggle-llm/` (file mode `0600`), one
file per notebook. This is how `connect()`, `stop()` and the command line find a server started elsewhere.

## Security and limitations

- **The endpoint is public and unauthenticated.** Anyone who knows the URL can use the model while the
  notebook runs. Do not send sensitive data.
- **The ngrok token is stored in the notebook.** Kaggle secrets are not available to notebooks started
  through the API, so the token is written into the notebook source. The notebook is always pushed as
  private; never make it public.
- **Kaggle's terms apply.** The free GPUs are intended for interactive and research use; run the server
  for the duration of your experiments, not as a permanent service.
- **One model per server.** Starting with a different model, context length or parallelism restarts the notebook.
- **Throughput is modest.** Expect roughly 15–20 tokens per second for a 9B model on a T4.
