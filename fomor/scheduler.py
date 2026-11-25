"""Minimal built-in scheduler: run one analysis pass per day at a fixed hour."""

from __future__ import annotations

import time
from pathlib import Path

from . import util
from .config import load_settings, paths
from .pipeline import analyze
from .storage import read_json, write_json


def run_due(root: str | Path | None = None) -> dict | None:
    settings = load_settings(root)
    state_path = paths(root)["scheduler"]
    state = read_json(state_path, {"last_run": None, "last_result": None})
    today = util.today_str()

    if state.get("last_run") == today:
        return None
    if util.now().hour < settings["analysis_hour"]:
        return None

    result = analyze(root)
    state["last_run"] = today
    state["last_result"] = result
    write_json(state_path, state)
    return result


def run_forever(root: str | Path | None = None, interval: int = 300) -> None:
    print(f"[fomor] scheduler started (interval={interval}s). Ctrl+C to stop.")
    while True:
        try:
            result = run_due(root)
            if result is not None:
                print(f"[fomor] analysis finished: {result.get('status')}")
        except Exception as exc:  # noqa: BLE001 - keep the daemon alive
            print(f"[fomor] analysis failed: {exc}")
        time.sleep(interval)
