# Configuration

All settings have defaults except `ngrok_authtoken`. Set them in any of these ways, from highest to lowest priority:

1. Keyword arguments to `start()`, `connect()`, `stop()`, `status()` or `session()`.
2. `kaggle_llm.configure(...)`, once per process.
3. Environment variables, useful for secrets in CI or a shell.

```python
import os
import kaggle_llm

kaggle_llm.configure(ngrok_authtoken=os.environ["MY_NGROK_TOKEN"], idle_minutes=60)
server = kaggle_llm.start(model="qwen3:14b")   # overrides the model for this call
```

`configure()` updates earlier calls; pass `None` to unset a value. `get_settings()` returns the settings in effect.

| Setting | Environment variable | Default | Description |
|---|---|---|---|
| `ngrok_authtoken` | `NGROK_AUTHTOKEN` | *required* | ngrok authtoken. |
| `ngrok_domain` | `NGROK_DOMAIN` | | Static ngrok domain. Without it, the URL changes on every start. |
| `kaggle_api_token` | `KAGGLE_API_TOKEN` | | Kaggle API token, if credentials are not configured on the machine. |
| `notebook_slug` | `KAGGLE_LLM_NOTEBOOK_SLUG` | `kaggle-llm-server` | Notebook name in your account. The username is detected. |
| `accelerator` | `KAGGLE_LLM_ACCELERATOR` | `NvidiaTeslaT4` | Kaggle accelerator. |
| `model` | `KAGGLE_LLM_MODEL` | `qwen3.5:9b` | Any model from the [Ollama library](https://ollama.com/library) that fits the GPU. |
| `context_length` | `KAGGLE_LLM_CONTEXT_LENGTH` | `32768` | Context window in tokens. Longer prompts are truncated from the start. |
| `num_parallel` | `KAGGLE_LLM_NUM_PARALLEL` | `1` | Requests processed concurrently. Each slot needs its own context memory. |
| `keep_alive` | `KAGGLE_LLM_KEEP_ALIVE` | `30m` | How long Ollama keeps the model in GPU memory between requests. |
| `idle_minutes` | `KAGGLE_LLM_IDLE_MINUTES` | `20` | Stop after this many minutes without requests. |
| `max_hours` | `KAGGLE_LLM_MAX_HOURS` | `4` | Stop after this many hours in total. |
| `wait_minutes` | `KAGGLE_LLM_WAIT_MINUTES` | `20` | How long `start()` waits for the server. |
| `state_dir` | `KAGGLE_LLM_STATE_DIR` | `~/.cache/kaggle-llm` | Where the URL and stop token of the running server are kept. |

!!! warning
    Avoid hard-coding tokens in code you share: read them from your own secret store or an environment variable.
