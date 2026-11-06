"""The `kaggle-llm` command. Secrets come from environment variables (e.g. NGROK_AUTHTOKEN)."""

from __future__ import annotations

import argparse
import sys

from kaggle_llm import lifecycle, notebook
from kaggle_llm.config import get_settings
from kaggle_llm.errors import KaggleLLMError

_START_OPTIONS = {
    "--model": str, "--context-length": int, "--num-parallel": int, "--ngrok-domain": str,
    "--idle-minutes": int, "--max-hours": float, "--wait-minutes": int,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kaggle-llm", description="Run an Ollama LLM on a Kaggle GPU.",
        epilog="The ngrok token is read from the NGROK_AUTHTOKEN environment variable.",
    )
    parser.add_argument("--notebook-slug", help="notebook name in your Kaggle account")
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="start the server, or reuse a running one")
    for option, kind in _START_OPTIONS.items():
        start.add_argument(option, type=kind)
    start.add_argument("--restart", action="store_true", help="start a new server even if one is running")
    start.add_argument("--no-wait", action="store_true", help="return once the notebook is pushed")
    commands.add_parser("status", help="show the notebook and server status")
    commands.add_parser("stop", help="stop the server")
    commands.add_parser("url", help="print the server URL")
    nb = commands.add_parser("notebook", help="write the notebook to run it by hand on kaggle.com")
    nb.add_argument("path", nargs="?", default="kaggle_llm_server.ipynb")
    nb.add_argument("--include-token", action="store_true", help="embed NGROK_AUTHTOKEN in the notebook")
    return parser


def _run(args: argparse.Namespace) -> int:
    common = {"notebook_slug": args.notebook_slug}
    if args.command == "start":
        names = [option[2:].replace("-", "_") for option in _START_OPTIONS]
        server = lifecycle.start(wait=not args.no_wait, restart=args.restart, **common,
                                 **{name: getattr(args, name) for name in names})
        if server.url:
            print(server.url)
    elif args.command == "status":
        current = lifecycle.status(**common)
        print(current)
        return 0 if current.ready else 1
    elif args.command == "stop":
        return 0 if lifecycle.stop(**common) else 1
    elif args.command == "url":
        print(lifecycle.url(**common))
    elif args.command == "notebook":
        notebook.write(args.path, get_settings(**common), include_token=args.include_token)
        print(f"Wrote {args.path}. Upload it to Kaggle, enable GPU and internet, then Run All.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return _run(args)
    except KaggleLLMError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nStopped waiting. The notebook keeps running; use `kaggle-llm stop` to stop it.",
              file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
