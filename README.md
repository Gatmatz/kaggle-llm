# kaggle-llm

[![PyPI](https://img.shields.io/pypi/v/kaggle-llm)](https://pypi.org/project/kaggle-llm/)
[![Python](https://img.shields.io/pypi/pyversions/kaggle-llm)](https://pypi.org/project/kaggle-llm/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
    extra_body={"reasoning_effort": "none"},       # skip the model's thinking: much faster
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

## How it works

```
your code ──HTTPS──▶ ngrok ──▶ proxy :8000 ──▶ Ollama :11434
                              └────────── private Kaggle notebook (GPU) ──────────┘
```

1. `start()` writes your settings into a notebook and pushes it to Kaggle as a private notebook with GPU and internet enabled.
2. The notebook installs Ollama, opens the tunnel, downloads the model and loads it into GPU memory.
3. `start()` finds the tunnel URL (your static ngrok domain, or the notebook's live log), waits until the model is ready, and returns a `Server`.
4. A small proxy in the notebook tracks activity and shuts the notebook down when it is idle or when you call `stop()`.

Your code, tools and agent loop run on your machine; the Kaggle GPU only generates the model's replies.

## Requirements

| | |
|---|---|
| Python | 3.10 or newer |
| Kaggle account | [Phone-verified](https://www.kaggle.com/settings), so notebooks get GPU and internet access |
| Kaggle API credentials | See [Kaggle credentials](#kaggle-credentials) |
| ngrok account | Free tier is enough. You need the [authtoken](https://dashboard.ngrok.com/get-started/your-authtoken); a [static domain](https://dashboard.ngrok.com/domains) is recommended |

Kaggle gives about 30 GPU hours per week; each session runs for at most 12 hours.

### Kaggle credentials

`kaggle-llm` uses the credentials of the official [`kaggle`](https://github.com/Kaggle/kaggle-api)
package. The simplest setup is one of:

```bash
kaggle auth login                     # once, signs in through the browser
export KAGGLE_API_TOKEN=your-token    # or a token from kaggle.com > Settings > API
```

The `kaggle` package uses the first credentials it finds, in this order:

| # | Source | How to create it |
|---|---|---|
| 1 | `KAGGLE_API_TOKEN` environment variable (the token, or a path to a file containing it) | kaggle.com > Settings > API > *Generate New Token* |
| 2 | `~/.kaggle/access_token` file | Save the same token in this file |
| 3 | `KAGGLE_USERNAME` and `KAGGLE_KEY` environment variables | Legacy API key |
| 4 | `~/.kaggle/kaggle.json` | Legacy API key file, `{"username": "...", "key": "..."}` |
| 5 | `~/.kaggle/credentials.json` | `kaggle auth login` |

To use a specific token from Python, for example on a machine that is not signed in, pass
`kaggle_api_token=` to `configure()` or `start()`. It is set as `KAGGLE_API_TOKEN` for the current
process, so it takes precedence over the sources above.

Your Kaggle username is read from these credentials. The credentials are only used on your machine to
call the Kaggle API (push the notebook, read its status and log). They are never written into the
notebook, and `kaggle-llm` does not store them.

## Installation

```bash
pip install kaggle-llm
```

`kaggle-llm` runs the model and tells you where it is. To talk to it, use the client of your agent
framework (it installs its own), or a plain SDK such as `pip install openai`.

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
    extra_body={"reasoning_effort": "none"},
)
print(reply.choices[0].message.content)

server.stop()                 # or let it stop itself after 20 idle minutes
```

The notebook is created in your Kaggle account as `kaggle-llm-server` on the first start and reused
afterwards. [`examples/quickstart.py`](examples/quickstart.py) shows chat, streaming and a tool-calling
agent loop:

```bash
export NGROK_AUTHTOKEN=your-ngrok-token
python examples/quickstart.py           # stops the server at the end
python examples/quickstart.py --keep    # leaves it running, so the next run starts immediately
```

## Connecting a client

A client needs three values:

| Client setting | Value | Example |
|---|---|---|
| Base URL | `server.openai_base_url` (OpenAI API) or `server.url` (Ollama API) | `https://<id>.ngrok-free.app/v1` |
| Model | `server.model` | `qwen3.5:9b` |
| API key | Any string; it is not checked | `"ollama"` |

Use the OpenAI-compatible API unless your framework only supports Ollama: nearly every framework speaks it.

## Thinking

Reasoning models such as Qwen 3.5 think before every answer. That improves hard answers, but makes
each agent step several times slower: a one-word reply takes about 8 s with thinking and 1 s without.
Thinking is on by default for these models; turn it off per client or per request.

| API | Thinking off | Thinking on |
|---|---|---|
| OpenAI-compatible | `extra_body={"reasoning_effort": "none"}` | omit the parameter |
| Ollama | `think=False` | `think=True` |

`extra_body={"think": False}` has no effect on the OpenAI-compatible API. With thinking on, the
OpenAI-compatible API returns only the final answer; the Ollama API returns the reasoning separately in
`message.thinking`.

## Using it in agents

All examples assume a running server:

```python
import kaggle_llm

server = kaggle_llm.start()      # or kaggle_llm.connect() if it is already running


def get_weather(city: str) -> str:
    """Current weather for a city."""
    return f"Sunny in {city}"
```

### OpenAI Agents SDK

`pip install openai-agents`

```python
from agents import Agent, ModelSettings, OpenAIChatCompletionsModel, Runner, function_tool, set_tracing_disabled
from openai import AsyncOpenAI

set_tracing_disabled(True)  # otherwise the SDK sends traces to OpenAI

client = AsyncOpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)
agent = Agent(
    name="assistant",
    instructions="Use tools when useful.",
    tools=[function_tool(get_weather)],
    model=OpenAIChatCompletionsModel(model=server.model, openai_client=client),
    model_settings=ModelSettings(extra_body={"reasoning_effort": "none"}),
)
print(Runner.run_sync(agent, "What is the weather in Thessaloniki?").final_output)
```

Use `OpenAIChatCompletionsModel`, not the SDK's default Responses API model.

### LangChain and LangGraph

`pip install langchain-openai langgraph`

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

llm = ChatOpenAI(
    base_url=server.openai_base_url,
    api_key="ollama",
    model=server.model,
    timeout=300,
    extra_body={"reasoning_effort": "none"},
)
agent = create_react_agent(llm, tools=[get_weather])
result = agent.invoke({"messages": [("user", "What is the weather in Thessaloniki?")]})
print(result["messages"][-1].content)
```

### Strands Agents

`pip install "strands-agents[ollama]"`

```python
from strands import Agent, tool
from strands.models.ollama import OllamaModel

model = OllamaModel(server.url, model_id=server.model, additional_args={"think": False})
agent = Agent(model=model, tools=[tool(get_weather)])
agent("What is the weather in Thessaloniki?")
```

### Without a framework

The OpenAI SDK with your own tool loop: see [`examples/quickstart.py`](examples/quickstart.py).

```python
from openai import OpenAI

client = OpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)
response = client.chat.completions.create(
    model=server.model,
    messages=[{"role": "user", "content": "What is the weather in Thessaloniki?"}],
    tools=[{"type": "function", "function": {
        "name": "get_weather",
        "description": "Current weather for a city.",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
    }}],
    extra_body={"reasoning_effort": "none"},
)
print(response.choices[0].message.tool_calls)
```

## Running experiments

### Startup time

Starting a server takes about 5 minutes: Kaggle assigns a GPU, the notebook installs Ollama, then it
downloads the model (about 6 GB for `qwen3.5:9b`) and loads it into GPU memory. Kaggle wipes the
notebook's disk when a session ends, so **every new session repeats these steps**, not only the first.

A running server is reused instantly. It keeps running until it has been idle for `idle_minutes`
(default 20), reaches `max_hours`, or you call `stop()`. To avoid waiting, keep one server running for
your whole working session, and raise `idle_minutes` if your experiments have long pauses.

### Workflow

Start the server once, then run your scripts against it as often as you like:

```bash
export NGROK_AUTHTOKEN=your-ngrok-token
kaggle-llm start
python experiment.py     # uses kaggle_llm.connect()
python experiment.py     # same server, no new notebook
kaggle-llm stop
```

`connect()` never starts a notebook, so a script cannot spend GPU quota by accident. `start()` reuses a
running server when its model, context length and parallelism match. `session()` starts and stops one
around a block:

```python
with kaggle_llm.session(model="qwen3:14b", idle_minutes=60) as server:
    ...
```

## Configuration

All settings have defaults except `ngrok_authtoken`. Set them in any of these ways, from highest to lowest priority:

1. Keyword arguments to `start()`, `connect()`, `stop()`, `status()` or `session()`.
2. `kaggle_llm.configure(...)`, once per process.
3. Environment variables, useful for secrets in CI or a shell.

```python
kaggle_llm.configure(ngrok_authtoken=os.environ["MY_NGROK_TOKEN"], idle_minutes=60)
server = kaggle_llm.start(model="qwen3:14b")   # overrides the model for this call
```

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

Avoid hard-coding tokens in code you share: read them from your own secret store or an environment variable.

## Command line

| Command | Description |
|---|---|
| `kaggle-llm start` | Start the server, or reuse a matching one. Options: `--model`, `--context-length`, `--num-parallel`, `--ngrok-domain`, `--idle-minutes`, `--max-hours`, `--wait-minutes`, `--restart`, `--no-wait`. |
| `kaggle-llm status` | Show the notebook and server status. Exits 0 when the server is ready. |
| `kaggle-llm stop` | Stop the server. |
| `kaggle-llm url` | Print the server URL. |
| `kaggle-llm notebook [PATH]` | Write the notebook to run it manually on kaggle.com (reads the ngrok token from the Kaggle secret `NGROK_AUTHTOKEN`). |

All commands accept `--notebook-slug`. The CLI reads the ngrok token from `NGROK_AUTHTOKEN`.

## Python API

| | |
|---|---|
| `configure(**settings) -> Settings` | Set defaults for this process. |
| `start(settings=None, *, wait=True, restart=False, quiet=False, **overrides) -> Server` | Start or reuse the server. |
| `connect(settings=None, *, require_ready=True, **overrides) -> Server` | Attach to a running server. |
| `session(settings=None, *, stop_on_exit=True, **kwargs)` | Context manager around `start()` and `stop()`. |
| `stop(...) -> bool` · `status(...) -> Status` · `url(...) -> str` | Lifecycle helpers. |
| `Server.openai_base_url`, `.url`, `.model` | Connection details. |
| `Server.info()`, `.is_ready()`, `.stop()` | Server state. |
| `Settings`, `get_settings(**overrides)` | The settings in effect. |
| `NGROK_HEADERS` | Headers that skip ngrok's browser warning page, for clients that send a browser user agent. |

Errors derive from `KaggleLLMError`: `ConfigError`, `KaggleError`, `QuotaExceededError` and `ServerNotReadyError`.

## Choosing a model

Kaggle's T4 and P100 GPUs have 16 GB of memory each. As a rule of thumb, quantised models up to about
14B parameters fit with a 32k context. For agents, pick a model tagged *tools* in the Ollama library,
such as `qwen3.5:9b` or `qwen3:14b`. Raising `context_length` or `num_parallel` increases memory use.

## Security and limitations

- **The endpoint is public and unauthenticated.** Anyone who knows the URL can use the model while the notebook runs. Do not send sensitive data.
- **The ngrok token is stored in the notebook.** Kaggle secrets are not available to notebooks started through the API, so the token is written into the notebook source. The notebook is always pushed as private; never make it public.
- **Kaggle's terms apply.** The free GPUs are intended for interactive and research use; run the server for the duration of your experiments, not as a permanent service.
- **One model per server.** Starting with a different model, context length or parallelism restarts the notebook.
- **Throughput is modest.** Expect roughly 15–20 tokens per second for a 9B model on a T4.

## Troubleshooting

| Problem | Solution |
|---|---|
| `No Kaggle credentials found` | Run `kaggle auth login`, or set `KAGGLE_API_TOKEN`. See [Kaggle credentials](#kaggle-credentials). |
| `HTTP 409` when starting | The notebook is already running. Run `kaggle-llm stop`, or stop the session on kaggle.com. |
| `QuotaExceededError` | The weekly GPU quota is used up. It resets weekly. |
| Notebook fails without internet | Verify your phone number in your Kaggle account settings. |
| Slow responses | Turn thinking off (see [Thinking](#thinking)), or use a smaller model. |
| Requests time out | Long generations can take minutes; raise your client's timeout (e.g. `timeout=300`). |
| Answers ignore early instructions | The prompt exceeds the context window. Raise `context_length`. |
| Need the notebook output | `kaggle kernels logs <your-username>/kaggle-llm-server` |

## Development

```bash
git clone <repository-url> && cd kaggle-llm
uv sync
uv run pytest
uv run ruff check src tests examples
```

The tests run locally against a fake Ollama server; they do not use Kaggle or ngrok.

## License

[MIT](LICENSE)
