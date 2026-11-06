# Contributing

Thanks for your interest in improving kaggle-llm. Bug reports, documentation fixes and pull requests are welcome.

## Development setup

You need [uv](https://docs.astral.sh/uv/) and Python 3.10 or newer.

```bash
git clone https://github.com/Gatmatz/kaggle-llm.git
cd kaggle-llm
uv sync
```

## Checks

Run these before opening a pull request; CI runs the same commands.

```bash
uv run ruff check src tests examples   # lint
uv run pytest                          # tests, against a fake Ollama server
uv run --group docs mkdocs build --strict   # documentation
```

The tests do not use Kaggle or ngrok. To try a change against a real server, run
`examples/quickstart.py` with your own credentials (see the
[documentation](https://gatmatz.github.io/kaggle-llm/getting-started/)).

Preview the documentation locally with `uv run --group docs mkdocs serve`.

## Project layout

| Path | Contents |
|---|---|
| `src/kaggle_llm/lifecycle.py` | `start`, `connect`, `stop`, `status`: the public lifecycle API |
| `src/kaggle_llm/config.py` | Settings, `configure()` and environment variables |
| `src/kaggle_llm/_kaggle.py` | Wrapper around the official `kaggle` package |
| `src/kaggle_llm/notebook.py` | Builds the Kaggle notebook |
| `src/kaggle_llm/remote/server.py` | Runs inside the notebook: Ollama, the proxy and the tunnel |
| `src/kaggle_llm/cli.py` | The `kaggle-llm` command |
| `docs/` | Documentation site (MkDocs) |

`remote/server.py` is pasted into the notebook as is, so it may only import the standard library,
`aiohttp` and `pyngrok`.

## Commit messages

Commits follow [Conventional Commits](https://www.conventionalcommits.org/). The type decides the next version:

| Commit | Example | Release |
|---|---|---|
| `fix:` | `fix: retry when the tunnel URL is not in the log yet` | patch |
| `feat:` | `feat: add a think setting to the server` | minor |
| `feat!:` or a `BREAKING CHANGE:` footer | `feat!: rename notebook_slug to notebook` | minor before 1.0, major after |
| `docs:`, `test:`, `ci:`, `refactor:`, `chore:` | `docs: explain startup time` | none |

## Pull requests

1. Create a branch from `main`.
2. Make your change with tests and documentation.
3. Make sure the checks pass.
4. Open a pull request with a Conventional Commits title; it is used as the squash-merge commit message.

## Releases

Releases are automated with [release-please](https://github.com/googleapis/release-please):

1. Every push to `main` updates an open *release pull request* with the next version number and the
   changelog, both derived from the commit messages.
2. Merging the release pull request tags the version, creates a GitHub release, and publishes the
   package to PyPI.

The documentation is rebuilt and deployed to GitHub Pages on every push to `main`.

### One-time repository setup (maintainers)

- **GitHub Pages:** *Settings > Pages > Source:* GitHub Actions.
- **Release pull requests:** *Settings > Actions > General:* allow GitHub Actions to create and approve pull requests.
- **PyPI:** add a [trusted publisher](https://docs.pypi.org/trusted-publishers/) for project `kaggle-llm`
  with owner `Gatmatz`, repository `kaggle-llm`, workflow `release.yml` and environment `pypi`. No API
  token is needed.
