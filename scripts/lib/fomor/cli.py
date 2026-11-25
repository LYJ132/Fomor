"""Command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .config import ensure_initialized, load_config, save_config
from .paths import FomorPaths
from .pipeline import run_analysis
from .prompts import describe_tasks
from .scheduler import catch_up, catch_up_inline
from .store import (
    append_event,
    iter_events,
    list_discoveries,
    list_topics,
    load_state,
    normalize_hook_payload,
)
from .utils import to_iso, utcnow


def _paths(args: argparse.Namespace) -> FomorPaths:
    return FomorPaths.resolve(getattr(args, "home", None))


def _read_hook_payload() -> dict[str, Any] | None:
    raw = sys.stdin.read()
    if not raw.strip():
        return None
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be a JSON object")
    return payload


def cmd_init(args: argparse.Namespace) -> int:
    paths = _paths(args)
    config = ensure_initialized(paths)
    print(f"initialized: {paths.root}")
    print(f"schedule: every day at {config['schedule']['hour']:02d}:{config['schedule']['minute']:02d} ({config['timezone']})")
    print(f"retention: events={config['retention']['event_days']}d feedback={config['retention']['feedback_days']}d")
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    """Fast, non-blocking UserPromptSubmit hook. Never breaks the user's turn."""
    try:
        payload = _read_hook_payload()
        if not payload:
            return 0
        paths = _paths(args)
        config = ensure_initialized(paths)
        payload.setdefault("platform", "trae")
        event = normalize_hook_payload(payload)
        if not event["user_message"]:
            return 0
        _, duplicate = append_event(paths, config, event)
        if duplicate:
            print("duplicate event skipped", file=sys.stderr)
        return 0
    except Exception as error:  # hooks must not block the agent
        print(f"fomor hook error: {error}", file=sys.stderr)
        return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = _paths(args)
    config = ensure_initialized(paths)
    state = load_state(paths)
    events = list(iter_events(paths))
    pending = list_discoveries(paths, status="observing")
    promoted = list_discoveries(paths, status="promoted")
    schedule = catch_up_inline(paths, config)
    print(f"home: {paths.root}")
    print(f"events: {len(events)}")
    print(f"topics: {len(list_topics(paths))}")
    print(f"discoveries: pending={len(pending)} promoted={len(promoted)}")
    print(f"last_success_at: {state.get('last_success_at', 'never')}")
    print(f"next_03:00_due: {'yes' if schedule['due'] else 'no'}")
    print(f"latest_cutoff: {schedule['latest_cutoff']}")
    print(f"report: {paths.reports_dir / 'latest.md'}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    paths = _paths(args)
    config = ensure_initialized(paths)
    if args.llm:
        config["llm"]["mode"] = args.llm
        save_config(paths, config)
    result = run_analysis(
        paths,
        config=config,
        scheduled=args.scheduled,
        make_backup=not args.no_backup,
    )
    if result["status"] == "skipped":
        print(result.get("report") or "skipped")
        return 0
    print(result["report"])
    return 0 if result["status"] == "completed" else 1


def cmd_catch_up(args: argparse.Namespace) -> int:
    paths = _paths(args)
    config = ensure_initialized(paths)
    if args.foreground:
        state = catch_up_inline(paths, config)
        if not state["due"]:
            print("not due")
            return 0
        result = run_analysis(paths, config=config, scheduled=True)
        print(result.get("report") or result["status"])
        return 0 if result["status"] == "completed" else 1
    result = catch_up(paths, config=config, detach=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_prompts(args: argparse.Namespace) -> int:
    for name in ["system", *describe_tasks()]:
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    # ``--home`` is accepted both before and after the subcommand so the
    # detached catch-up command can be written unambiguously.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", default=argparse.SUPPRESS, help="data directory, default ~/.fomor")

    parser = argparse.ArgumentParser(prog="fomor", description="Fomor local exploration assistant")
    parser.add_argument("--home", default=None, help="data directory, default ~/.fomor")
    parser.add_argument("--version", action="version", version=f"fomor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", parents=[common], help="create ~/.fomor and default settings")
    init.set_defaults(func=cmd_init)

    hook = sub.add_parser("hook", parents=[common], help="read a Trae UserPromptSubmit payload from stdin")
    hook.set_defaults(func=cmd_hook)

    status = sub.add_parser("status", parents=[common], help="show counts and schedule state")
    status.set_defaults(func=cmd_status)

    analyze = sub.add_parser("analyze", parents=[common], help="run feedback review and analysis")
    analyze.add_argument("--scheduled", action="store_true", help="only run when the 03:00 cutoff is due")
    analyze.add_argument("--llm", choices=["mock", "traecli", "openai"], help="override llm mode")
    analyze.add_argument("--no-backup", action="store_true")
    analyze.set_defaults(func=cmd_analyze)

    catch = sub.add_parser("catch-up", parents=[common], help="spawn analysis if the 03:00 run was missed")
    catch.add_argument("--foreground", action="store_true", help="run inline instead of spawning")
    catch.set_defaults(func=cmd_catch_up)

    prompts = sub.add_parser("prompts", parents=[common], help="list prompt tasks")
    prompts.set_defaults(func=cmd_prompts)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
