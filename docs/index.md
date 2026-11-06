# kaggle-llm

Run an open-weight LLM on a free Kaggle GPU and use it from your code and agents, as if it were a hosted API.

`kaggle-llm` pushes a private notebook to Kaggle that serves a model with [Ollama](https://ollama.com),
exposes it through an [ngrok](https://ngrok.com) tunnel, and tells you where it is. The server speaks the
OpenAI and Ollama APIs, so any client or agent framework can use it, including tool calling and streaming.

```python
import kaggle_llm
from openai import OpenAI

server = kaggle_llm.start(ngrok_authtoken="...")   # GPU notebook up, model loaded

client = OpenAI(base_url=server.openai_base_url, api_key="ollama")
reply = client.chat.completions.create(
    model=server.model,
    messages=[{"role": "user", "content": "Explain tunnelling in one sentence."}],
    extra_body={"reasoning_effort": "none"},
)
print(reply.choices[0].message.content)

server.stop()
```

## Features

- **One call to a GPU-backed model.** `start()` pushes the notebook, follows its progress and returns once the model answers.
- **Standard APIs.** An OpenAI-compatible `/v1` endpoint and the native Ollama API, with tool calling and streaming.
- **Works with any client.** The OpenAI or Ollama SDKs, the OpenAI Agents SDK, LangChain, Strands Agents or plain HTTP.
- **Configured in Python.** No config files. Your Kaggle username is detected automatically.
- **Saves your GPU quota.** The notebook stops itself when idle, after a time limit, or on `stop()`, and never in the middle of a request.
- **Reuse across processes.** Start the server once, then connect to it from any script or notebook.
- **Minimal dependencies.** Only `kaggle` and `requests`.

## Next steps

- [Getting started](getting-started.md): requirements, credentials and your first request.
- [Connecting clients and agents](agents.md): the OpenAI Agents SDK, LangChain, Strands and more.
- [Running experiments](experiments.md): keep one server running across many scripts.
