# kaggle-llm

[![CI](https://github.com/Gatmatz/kaggle-llm/actions/workflows/ci.yml/badge.svg)](https://github.com/Gatmatz/kaggle-llm/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kaggle-llm)](https://pypi.org/project/kaggle-llm/)
[![Python](https://img.shields.io/pypi/pyversions/kaggle-llm)](https://pypi.org/project/kaggle-llm/)
[![Docs](https://img.shields.io/badge/docs-gatmatz.github.io-blue)](https://gatmatz.github.io/kaggle-llm/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Run an open-weight LLM on a free Kaggle GPU and use it from your code and agents, as if it were a hosted API.

`kaggle-llm` pushes a private notebook to Kaggle that serves a model with [Ollama](https://ollama.com),
exposes it through an [ngrok](https://ngrok.com) tunnel, and tells you where it is. The server speaks the
OpenAI and Ollama APIs, so any client or agent framework can use it, including tool calling and streaming.

**[Documentation](https://gatmatz.github.io/kaggle-llm/)**

## Features

- **One call to a GPU-backed model.** `start()` pushes the notebook, follows its progress and returns once the model answers.
- **Standard APIs.** An OpenAI-compatible `/v1` endpoint and the native Ollama API, with tool calling and streaming.
- **Works with any client.** The OpenAI or Ollama SDKs, the OpenAI Agents SDK, LangChain, Strands Agents or plain HTTP.
- **Configured in Python.** No config files. Your Kaggle username is detected automatically.
- **Saves your GPU quota.** The notebook stops itself when idle, after a time limit, or on `stop()`.
- **Reuse across processes.** Start the server once, then connect to it from any script.

## Requirements

- Python 3.10+
- A [phone-verified](https://www.kaggle.com/settings) Kaggle account, signed in with `kaggle auth login`
- An [ngrok](https://dashboard.ngrok.com/get-started/your-authtoken) authtoken (free tier)

## Installation

```bash
pip install kaggle-llm
```

## Quick start

```python
import kaggle_llm
from openai import OpenAI

kaggle_llm.configure(ngrok_authtoken="your-ngrok-token", model="qwen3.5:9b")

server = kaggle_llm.start()   # about 5 minutes, unless a matching server is already running
client = OpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)

reply = client.chat.completions.create(
    model=server.model,
    messages=[{"role": "user", "content": "Hello!"}],
    extra_body={"reasoning_effort": "none"},   # skip the model's thinking: much faster
)
print(reply.choices[0].message.content)

server.stop()                 # or let it stop itself after 20 idle minutes
```

## Use it in an agent

Any framework only needs the base URL and the model name. With the
[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/):

```python
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from openai import AsyncOpenAI

set_tracing_disabled(True)

@function_tool
def get_weather(city: str) -> str:
    return f"Sunny in {city}"

client = AsyncOpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)
agent = Agent(
    name="assistant",
    tools=[get_weather],
    model=OpenAIChatCompletionsModel(model=server.model, openai_client=client),
    model_settings=ModelSettings(extra_body={"reasoning_effort": "none"}),
)
print(Runner.run_sync(agent, "What is the weather in Thessaloniki?").final_output)
```

LangChain, Strands Agents and others: see
[Connecting clients and agents](https://gatmatz.github.io/kaggle-llm/agents/).

## Command line

```bash
export NGROK_AUTHTOKEN=your-ngrok-token
kaggle-llm start      # start once per working session
kaggle-llm status
kaggle-llm stop
```

Scripts then attach to the running server with `kaggle_llm.connect()`.

## Documentation

- [Getting started](https://gatmatz.github.io/kaggle-llm/getting-started/): requirements, credentials, first request
- [Running experiments](https://gatmatz.github.io/kaggle-llm/experiments/): startup time and the CLI workflow
- [Configuration](https://gatmatz.github.io/kaggle-llm/configuration/) and [Python API](https://gatmatz.github.io/kaggle-llm/api/)
- [How it works](https://gatmatz.github.io/kaggle-llm/how-it-works/), including security and limitations

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
