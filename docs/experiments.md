# Running experiments

## Startup time

Starting a server takes about 5 minutes: Kaggle assigns a GPU, the notebook installs Ollama, then it
downloads the model (about 6 GB for `qwen3.5:9b`) and loads it into GPU memory. Kaggle wipes the
notebook's disk when a session ends, so **every new session repeats these steps**, not only the first.

A running server is reused instantly. It keeps running until it has been idle for `idle_minutes`
(default 20), reaches `max_hours`, or you call `stop()`. To avoid waiting, keep one server running for
your whole working session, and raise `idle_minutes` if your experiments have long pauses.

## Workflow

Start the server once from the command line, then run your scripts against it as often as you like:

```bash
export NGROK_AUTHTOKEN=your-ngrok-token
kaggle-llm start         # wait for "Ready at https://..."
python experiment.py     # uses kaggle_llm.connect()
python experiment.py     # same server, no new notebook
kaggle-llm stop
```

In each script:

```python
import kaggle_llm
from openai import OpenAI

server = kaggle_llm.connect()    # finds the running server; never starts one
client = OpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)
```

- `connect()` does not need the ngrok token and takes the model name from the running server.
- If no server is running, `connect()` raises `ServerNotReadyError` instead of starting one, so a script
  cannot spend GPU quota by accident.
- The command line and Python share the server's URL and stop token (kept in `~/.cache/kaggle-llm`), so
  you can start from one and stop from the other.
- `kaggle-llm status` shows whether the server is up at any time.

## From Python only

`start()` reuses a running server when its model, context length and parallelism match, and starts one
otherwise. `session()` starts and stops a server around a block:

```python
with kaggle_llm.session(model="qwen3:14b", idle_minutes=60) as server:
    ...
# the server is stopped here
```

Starting with a different model, context length or parallelism stops the running server and starts a
new one, which takes the full startup time again.
