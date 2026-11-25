"""Event collection: recording, reading, marking analysed and cleanup.

An *Event* is one raw question the user sent to an agent platform.  Events are
short-lived: per the PRD they are removed after ``retention_hours`` and must
never be the sole reason a long-term Topic disappears.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Iterable

from . import util
from .config import load_settings, paths
from .storage import FileLock, read_json, write_json


def _event_file(date: str, root: str | Path | None = None) -> Path:
    return paths(root)["events"] / f"{date}.json"


def _empty_day(date: str) -> dict:
    return {"date": date, "events": []}


def record_event(
    message: str,
    *,
    platform: str = "manual",
    session_id: str | None = None,
    timestamp: str | None = None,
    event_id: str | None = None,
    root: str | Path | None = None,
) -> dict:
    """Append one event.  Idempotent on ``event_id``."""
    message = (message or "").strip()
    if not message:
        raise ValueError("user message must not be empty")

    event = {
        "event_id": event_id or util.new_id("evt"),
        "platform": platform,
        "session_id": session_id or "unknown",
        "timestamp": timestamp or util.now_iso(),
        "user_message": message,
        "collection_status": "collected",
        "related_topic_id": None,
        "analyzed_at": None,
    }
    date = event["timestamp"][:10]
    path = _event_file(date, root)

    with FileLock(path.with_suffix(".lock")):
        data = read_json(path, _empty_day(date))
        for existing in data["events"]:
            if existing["event_id"] == event["event_id"]:
                return existing
        data["events"].append(event)
        write_json(path, data)
    return event


def import_events(items: Iterable[dict], root: str | Path | None = None) -> list[dict]:
    """Import user-supplied event dicts (used by file import / demo data)."""
    created = []
    for item in items:
        created.append(
            record_event(
                item.get("user_message") or item.get("message", ""),
                platform=item.get("platform", "import"),
                session_id=item.get("session_id"),
                timestamp=item.get("timestamp"),
                event_id=item.get("event_id"),
                root=root,
            )
        )
    return created


def load_day(date: str, root: str | Path | None = None) -> list[dict]:
    data = read_json(_event_file(date, root), _empty_day(date))
    return data.get("events", [])


def pending_events(root: str | Path | None = None, lookback_days: int = 2) -> list[dict]:
    """Events not yet analysed, newest last."""
    today = dt.date.today()
    result: list[dict] = []
    for offset in range(lookback_days, -1, -1):
        day = (today - dt.timedelta(days=offset)).strftime("%Y-%m-%d")
        for event in load_day(day, root):
            if not event.get("analyzed_at"):
                result.append(event)
    return result


def all_events(root: str | Path | None = None) -> list[dict]:
    result: list[dict] = []
    for path in sorted(paths(root)["events"].glob("*.json")):
        if path.name.endswith(".lock"):
            continue
        data = read_json(path, {"events": []})
        result.extend(data.get("events", []))
    return result


def mark_analyzed(
    event_ids: Iterable[str],
    *,
    topic_id: str | None = None,
    root: str | Path | None = None,
) -> int:
    wanted = set(event_ids)
    if not wanted:
        return 0
    stamped = util.now_iso()
    changed = 0
    for path in sorted(paths(root)["events"].glob("*.json")):
        if path.name.endswith(".lock"):
            continue
        with FileLock(path.with_suffix(".lock")):
            data = read_json(path, {"events": []})
            touched = False
            for event in data.get("events", []):
                if event["event_id"] in wanted and not event.get("analyzed_at"):
                    event["analyzed_at"] = stamped
                    if topic_id:
                        event["related_topic_id"] = topic_id
                    touched = True
                    changed += 1
            if touched:
                write_json(path, data)
    return changed


def cleanup_expired(root: str | Path | None = None, retention_hours: int | None = None) -> dict:
    """Delete whole event files older than the retention window.

    Only raw events are removed; Topics and Discoveries are untouched.
    """
    settings = load_settings(root)
    hours = retention_hours if retention_hours is not None else settings["retention_hours"]
    cutoff = dt.date.today() - dt.timedelta(hours=hours)
    removed_days = 0
    removed_events = 0
    for path in sorted(paths(root)["events"].glob("*.json")):
        if path.name.endswith(".lock"):
            continue
        try:
            day = dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if day < cutoff:
            data = read_json(path, {"events": []})
            removed_events += len(data.get("events", []))
            path.unlink(missing_ok=True)
            removed_days += 1
    return {"removed_days": removed_days, "removed_events": removed_events}
