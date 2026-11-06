# Connecting clients and agents

## What a client needs

| Client setting | Value | Example |
|---|---|---|
| Base URL | `server.openai_base_url` (OpenAI API) or `server.url` (Ollama API) | `https://<id>.ngrok-free.app/v1` |
| Model | `server.model` | `qwen3.5:9b` |
| API key | Any string; it is not checked | `"ollama"` |

Use the OpenAI-compatible API unless your framework only supports Ollama: nearly every framework speaks it.
Agent frameworks install their own client library, so you do not need to install `openai` or `ollama` yourself.

Your tools, memory and agent loop run on your machine; the Kaggle GPU only generates the model's replies.

All examples below assume a running server and this tool:

```python
import kaggle_llm

server = kaggle_llm.start()      # or kaggle_llm.connect() if it is already running


def get_weather(city: str) -> str:
    """Current weather for a city."""
    return f"Sunny in {city}"
```

## OpenAI Agents SDK

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

## LangChain and LangGraph

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

## Strands Agents

`pip install "strands-agents[ollama]"`

```python
from strands import Agent, tool
from strands.models.ollama import OllamaModel

model = OllamaModel(server.url, model_id=server.model, additional_args={"think": False})
agent = Agent(model=model, tools=[tool(get_weather)])
agent("What is the weather in Thessaloniki?")
```

## Ollama SDK

`pip install ollama`

```python
from ollama import Client

client = Client(host=server.url, timeout=300)
reply = client.chat(model=server.model, messages=[{"role": "user", "content": "Hi"}], think=False)
print(reply.message.content)
```

## Without a framework

The OpenAI SDK with your own tool loop: see
[`examples/quickstart.py`](https://github.com/Gatmatz/kaggle-llm/blob/main/examples/quickstart.py).

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

## Choosing a model

Kaggle's T4 and P100 GPUs have 16 GB of memory each. As a rule of thumb, quantised models up to about
14B parameters fit with a 32k context. For agents, pick a model tagged *tools* in the
[Ollama library](https://ollama.com/library), such as `qwen3.5:9b` or `qwen3:14b`. Raising
`context_length` or `num_parallel` increases memory use.
