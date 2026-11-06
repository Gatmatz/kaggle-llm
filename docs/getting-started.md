# Getting started

## Requirements

| | |
|---|---|
| Python | 3.10 or newer |
| Kaggle account | [Phone-verified](https://www.kaggle.com/settings), so notebooks get GPU and internet access |
| Kaggle API credentials | See [Kaggle credentials](#kaggle-credentials) |
| ngrok account | Free tier is enough. You need the [authtoken](https://dashboard.ngrok.com/get-started/your-authtoken); a [static domain](https://dashboard.ngrok.com/domains) is recommended |

Kaggle gives about 30 GPU hours per week; each session runs for at most 12 hours.

## Installation

```bash
pip install kaggle-llm
```

`kaggle-llm` runs the model and tells you where it is. To talk to it, use the client of your agent
framework (it installs its own), or a plain SDK such as `pip install openai`.

## Kaggle credentials

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

## First request

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
afterwards.

## Example script

[`examples/quickstart.py`](https://github.com/Gatmatz/kaggle-llm/blob/main/examples/quickstart.py)
runs a chat, a streamed reply and a small tool-calling agent:

```bash
export NGROK_AUTHTOKEN=your-ngrok-token
python examples/quickstart.py           # stops the server at the end
python examples/quickstart.py --keep    # leaves it running, so the next run starts immediately
```
