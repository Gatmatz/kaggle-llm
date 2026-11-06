# Troubleshooting

| Problem | Solution |
|---|---|
| `No Kaggle credentials found` | Run `kaggle auth login`, or set `KAGGLE_API_TOKEN`. See [Kaggle credentials](getting-started.md#kaggle-credentials). |
| `No ngrok authtoken` | Pass `ngrok_authtoken=` or set `NGROK_AUTHTOKEN`. |
| `HTTP 409` when starting | The notebook is already running. Run `kaggle-llm stop`, or stop the session on kaggle.com. |
| `QuotaExceededError` | The weekly GPU quota is used up. It resets weekly. |
| Notebook fails without internet | Verify your phone number in your Kaggle account settings. |
| `ServerNotReadyError` from `connect()` | No server is running. Start one with `kaggle-llm start`. |
| Slow responses | Turn thinking off (see [Thinking models](thinking.md)), or use a smaller model. |
| Requests time out | Long generations can take minutes; raise your client's timeout (e.g. `timeout=300`). |
| Answers ignore early instructions | The prompt exceeds the context window. Raise `context_length`. |
| Need the notebook output | `kaggle kernels logs <your-username>/kaggle-llm-server` |
