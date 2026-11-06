"""Start a model on Kaggle, then chat, stream and run a small tool-using agent.

    export NGROK_AUTHTOKEN=your-token
    uv run python examples/quickstart.py            # stops the server at the end
    uv run python examples/quickstart.py --keep     # leaves it running for the next script
"""

import json
import sys
import time

from openai import OpenAI

import kaggle_llm

kaggle_llm.configure(model="qwen3.5:9b")
NO_THINKING = {"reasoning_effort": "none"}  # thinking models answer much faster without it


def chat(client, model):
    started = time.time()
    reply = client.chat.completions.create(
        model=model, extra_body=NO_THINKING,
        messages=[{"role": "user", "content": "In one sentence, what is a GPU?"}],
    )
    print(f"{reply.choices[0].message.content}\n({time.time() - started:.1f}s)")


def stream(client, model):
    chunks = client.chat.completions.create(
        model=model, stream=True, extra_body=NO_THINKING,
        messages=[{"role": "user", "content": "Write a haiku about free GPUs."}],
    )
    for chunk in chunks:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()


TOOLS = {
    "get_weather": lambda city: {"city": city, "forecast": "sunny", "temperature_c": 24},
    "add": lambda a, b: {"result": a + b},
}
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_weather", "description": "Current weather for a city.",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "add", "description": "Add two numbers.",
        "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                       "required": ["a", "b"]}}},
]


def agent(client, model, question, max_steps=5):
    """The basic agent loop: the model asks for tools, we run them, until it answers."""
    messages = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        message = client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS, extra_body=NO_THINKING
        )
        message = message.choices[0].message
        if not message.tool_calls:
            return message.content
        messages.append(message)
        for call in message.tool_calls:
            arguments = json.loads(call.function.arguments)
            result = TOOLS[call.function.name](**arguments)
            print(f"  tool {call.function.name}({arguments}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    return "(no answer within the step limit)"


def main():
    server = kaggle_llm.start()  # reuses a running server with the same settings
    client = OpenAI(base_url=server.openai_base_url, api_key="ollama", timeout=300)
    try:
        print("\n== Chat")
        chat(client, server.model)
        print("\n== Streaming")
        stream(client, server.model)
        print("\n== Agent with tools")
        print(agent(client, server.model, "What's the weather in Thessaloniki, and what is 17.5 + 24.5?"))
    finally:
        if "--keep" in sys.argv:
            print(f"\nServer left running at {server.url}. Stop it with `kaggle-llm stop`.")
        else:
            server.stop()


if __name__ == "__main__":
    main()
