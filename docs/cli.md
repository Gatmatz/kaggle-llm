# Command line

| Command | Description |
|---|---|
| `kaggle-llm start` | Start the server, or reuse a matching one. Prints the URL when ready. |
| `kaggle-llm status` | Show the notebook and server status. Exits 0 when the server is ready. |
| `kaggle-llm stop` | Stop the server. |
| `kaggle-llm url` | Print the server URL. |
| `kaggle-llm notebook [PATH]` | Write the notebook to run it manually on kaggle.com. |

All commands accept `--notebook-slug`. The CLI reads the ngrok token from the `NGROK_AUTHTOKEN`
environment variable, and other settings from the environment variables listed in
[Configuration](configuration.md).

## `start` options

| Option | Description |
|---|---|
| `--model` | Ollama model. |
| `--context-length` | Context window in tokens. |
| `--num-parallel` | Requests processed concurrently. |
| `--ngrok-domain` | Static ngrok domain. |
| `--idle-minutes` | Stop after this many idle minutes. |
| `--max-hours` | Stop after this many hours. |
| `--wait-minutes` | How long to wait for the server. |
| `--restart` | Start a new server even if a matching one is running. |
| `--no-wait` | Return once the notebook is pushed. |

Interrupting `start` with Ctrl+C stops waiting, not the notebook.

## `notebook`

Writes the notebook so you can upload and run it by hand on kaggle.com (enable GPU and internet, then
*Run All*). It reads the ngrok token from the Kaggle secret `NGROK_AUTHTOKEN` unless you pass
`--include-token`.

## Example

```console
$ export NGROK_AUTHTOKEN=your-ngrok-token
$ kaggle-llm start --model qwen3:14b
Pushing gatmatz/kaggle-llm-server (qwen3:14b, context 32768, NvidiaTeslaT4)...
Version 6 started: https://www.kaggle.com/code/gatmatz/kaggle-llm-server
  kaggle: running, server: downloading qwen3:14b (42%)
Ready at https://xxxx.ngrok-free.dev. Stops after 20 idle minutes.
https://xxxx.ngrok-free.dev
$ kaggle-llm status
notebook  gatmatz/kaggle-llm-server/6: running
server    https://xxxx.ngrok-free.dev: ready
$ kaggle-llm stop
Stopping the server at https://xxxx.ngrok-free.dev.
```
