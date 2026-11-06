# Thinking models

Reasoning models such as Qwen 3.5 think before every answer. That improves hard answers, but makes
each agent step several times slower: a one-word reply takes about 8 s with thinking and 1 s without.
Thinking is on by default for these models; turn it off per client or per request.

| API | Thinking off | Thinking on |
|---|---|---|
| OpenAI-compatible | `extra_body={"reasoning_effort": "none"}` | omit the parameter |
| Ollama | `think=False` | `think=True` |

```python
# OpenAI-compatible API
client.chat.completions.create(..., extra_body={"reasoning_effort": "none"})

# Ollama API
client.chat(..., think=False)
```

How each framework sets it once for all requests:

| Framework | Setting |
|---|---|
| OpenAI Agents SDK | `ModelSettings(extra_body={"reasoning_effort": "none"})` |
| LangChain | `ChatOpenAI(..., extra_body={"reasoning_effort": "none"})` |
| Strands Agents | `OllamaModel(..., additional_args={"think": False})` |

!!! note
    `extra_body={"think": False}` has no effect on the OpenAI-compatible API. With thinking on, the
    OpenAI-compatible API returns only the final answer; the Ollama API returns the reasoning separately
    in `message.thinking`.
