"""03:00 schedule and first-wake catch-up (option 4)."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .paths import FomorPaths
from .store import load_state
from .utils import parse_iso, to_iso, utcnow


def latest_cutoff(now: datetime, config: dict[str, Any]) -> datetime:
    tz = ZoneInfo(config["timezone"])
    local = now.astimezone(tz)
    cutoff = local.replace(
        hour=int(config["schedule"]["hour"]),
        minute=int(config["schedule"]["minute"]),
        second=0,
        microsecond=0,
    )
    if local < cutoff:
        cutoff -= timedelta(days=1)
    return cutoff.astimezone(ZoneInfo("UTC"))


def next_cutoff(now: datetime, config: dict[str, Any]) -> datetime:
    return latest_cutoff(now, config) + timedelta(days=1)


def is_due(paths: FomorPaths, config: dict[str, Any], now: datetime | None = None) -> bool:
    moment = now or utcnow()
    state = load_state(paths)
    last = state.get("last_success_at")
    if not last:
        return True
    return parse_iso(last) < latest_cutoff(moment, config)


def catch_up(
    paths: FomorPaths,
    config: dict[str, Any],
    detach: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run catch-up analysis if the latest 03:00 cutoff was missed."""
    moment = now or utcnow()
    if not is_due(paths, config, moment):
        return {"status": "not_due", "checked_at": to_iso(moment)}

    command = [
        sys.executable,
        "-m",
        "fomor",
        "analyze",
        "--scheduled",
        "--home",
        str(paths.root),
    ]
    if not detach:
        return {"status": "running_inline", "command": command}

    paths.ensure()
    # ``python -m fomor`` needs the package importable no matter where the
    # SessionStart hook ran.  Point PYTHONPATH at the repository root.
    package_root = Path(__file__).resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(package_root), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(package_root)]
    )
    log_path = paths.logs_dir / "catchup.log"
    handle = log_path.open("a", encoding="utf-8")
    handle.write(f"\n[{to_iso(moment)}] catch-up start\n")
    handle.flush()
    process = subprocess.Popen(
        command,
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=str(package_root),
        env=env,
        start_new_session=True,
        close_fds=True,
    )
    return {"status": "spawned", "pid": process.pid, "log": str(log_path), "checked_at": to_iso(moment)}


def catch_up_inline(paths: FomorPaths, config: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    """Helper for tests / foreground CLI: return due status only."""
    moment = now or utcnow()
    return {
        "due": is_due(paths, config, moment),
        "latest_cutoff": to_iso(latest_cutoff(moment, config)),
        "next_cutoff": to_iso(next_cutoff(moment, config)),
    }
