"""Persistence for events, topics, discoveries and runtime state."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .paths import FomorPaths
from .utils import (
    append_jsonl,
    atomic_write_json,
    local_day,
    normalize_text,
    parse_iso,
    read_json,
    read_jsonl,
    sha256_text,
    to_iso,
    utcnow,
)

Event = dict[str, Any]
Topic = dict[str, Any]
Discovery = dict[str, Any]


def event_fingerprint(payload: dict[str, Any]) -> str:
    platform = str(payload.get("platform") or "trae")
    session = str(payload.get("session_id") or "")
    prompt = normalize_text(str(payload.get("user_message") or ""))
    return sha256_text(f"{platform}|{session}|{prompt}")


def normalize_hook_payload(payload: dict[str, Any], now: datetime | None = None) -> Event:
    moment = now or utcnow()
    prompt = str(payload.get("prompt") or payload.get("user_message") or "").strip()
    event: Event = {
        "event_id": payload.get("event_id") or f"evt_{moment.strftime('%Y%m%d%H%M%S')}_{sha256_text(prompt)[:6]}",
        "platform": payload.get("platform") or "trae",
        "session_id": str(payload.get("session_id") or ""),
        "timestamp": to_iso(moment),
        "user_message": prompt,
        "collection_status": "collected",
        "fingerprint": "",
        "related_topic_id": None,
        "analyzed_at": None,
        "metadata": {
            "cwd": payload.get("cwd"),
            "workspace_roots": payload.get("workspace_roots") or [],
            "hook_event_name": payload.get("hook_event_name") or "UserPromptSubmit",
        },
    }
    event["fingerprint"] = event_fingerprint(event)
    return event


def find_event_by_fingerprint(paths: FomorPaths, fingerprint: str, days: int) -> Event | None:
    cutoff = utcnow() - timedelta(days=days)
    for event in iter_events(paths, since=cutoff):
        if event.get("fingerprint") == fingerprint:
            return event
    return None


def append_event(paths: FomorPaths, config: dict[str, Any], event: Event) -> tuple[Event, bool]:
    """Append unless the same message was already collected recently."""
    days = int(config["retention"]["dedupe_days"])
    existing = find_event_by_fingerprint(paths, event["fingerprint"], days)
    if existing:
        return existing, True
    day = local_day(parse_iso(event["timestamp"]), config["timezone"])
    path = paths.event_file(day)
    append_jsonl(path, [event])
    return event, False


def iter_events(
    paths: FomorPaths,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Iterable[Event]:
    for path in sorted(paths.events_dir.glob("*.jsonl")):
        for event in read_jsonl(path):
            try:
                moment = parse_iso(event["timestamp"])
            except (KeyError, ValueError):
                continue
            if since and moment < since:
                continue
            if until and moment >= until:
                continue
            yield event


def mark_events_analyzed(paths: FomorPaths, events: list[Event], topic_id: str, at: datetime) -> None:
    """Rewrite only the affected daily files, preserving other records."""
    by_file: dict[Path, list[Event]] = {}
    ids = {event["event_id"] for event in events}
    if not ids:
        return
    for path in paths.events_dir.glob("*.jsonl"):
        records = list(read_jsonl(path))
        changed = False
        for record in records:
            if record.get("event_id") in ids:
                record["related_topic_id"] = topic_id
                record["analyzed_at"] = to_iso(at)
                changed = True
        if changed:
            by_file[path] = records
    for path, records in by_file.items():
        _rewrite_jsonl(path, records)


def _rewrite_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(path)


def save_topic(paths: FomorPaths, topic: Topic) -> None:
    atomic_write_json(paths.topics_dir / f"{topic['topic_id']}.json", topic)


def load_topic(paths: FomorPaths, topic_id: str) -> Topic | None:
    return read_json(paths.topics_dir / f"{topic_id}.json")


def list_topics(paths: FomorPaths) -> list[Topic]:
    topics = []
    for path in sorted(paths.topics_dir.glob("*.json")):
        payload = read_json(path)
        if payload:
            topics.append(payload)
    return topics


def save_discovery(paths: FomorPaths, discovery: Discovery) -> Path:
    status = discovery.get("status", "observing")
    directory = paths.promoted_dir if status == "promoted" else paths.pending_dir
    path = directory / f"{discovery['discovery_id']}.json"
    atomic_write_json(path, discovery)
    return path


def load_discovery(paths: FomorPaths, discovery_id: str) -> Discovery | None:
    for directory in (paths.pending_dir, paths.promoted_dir):
        payload = read_json(directory / f"{discovery_id}.json")
        if payload:
            return payload
    return None


def list_discoveries(paths: FomorPaths, status: str | None = None) -> list[Discovery]:
    result: list[Discovery] = []
    directories = []
    if status in (None, "observing"):
        directories.append(paths.pending_dir)
    if status in (None, "promoted"):
        directories.append(paths.promoted_dir)
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            payload = read_json(path)
            if payload:
                result.append(payload)
    return result


def promote_discovery(paths: FomorPaths, discovery: Discovery) -> None:
    discovery["status"] = "promoted"
    discovery["promoted_at"] = to_iso(utcnow())
    save_discovery(paths, discovery)
    pending = paths.pending_dir / f"{discovery['discovery_id']}.json"
    if pending.exists():
        pending.unlink()


def expire_discovery(paths: FomorPaths, discovery: Discovery, config: dict[str, Any]) -> None:
    pending = paths.pending_dir / f"{discovery['discovery_id']}.json"
    if pending.exists():
        pending.unlink()
    tombstone = {
        "discovery_id": discovery["discovery_id"],
        "topic_id": discovery.get("topic_id"),
        "fingerprint": sha256_text(
            " ".join(
                [
                    str(discovery.get("topic_name") or ""),
                    str(discovery.get("title") or ""),
                    " ".join(solution.get("name", "") for solution in discovery.get("other_solutions", [])),
                ]
            )
        ),
        "expired_at": to_iso(utcnow()),
        "retention_days": int(config["retention"]["tombstone_days"]),
    }
    atomic_write_json(paths.tombstones_dir / f"{discovery['discovery_id']}.json", tombstone)


def load_state(paths: FomorPaths) -> dict[str, Any]:
    return read_json(paths.state_file, default={}) or {}


def save_state(paths: FomorPaths, state: dict[str, Any]) -> None:
    atomic_write_json(paths.state_file, state)


def append_run(paths: FomorPaths, record: dict[str, Any]) -> None:
    runs = read_json(paths.runs_file, default={"runs": []}) or {"runs": []}
    runs.setdefault("runs", []).append(record)
    runs["runs"] = runs["runs"][-200:]
    atomic_write_json(paths.runs_file, runs)


def cleanup_events(paths: FomorPaths, config: dict[str, Any]) -> int:
    """Delete whole day files older than retention; never split a day."""
    cutoff = utcnow() - timedelta(days=int(config["retention"]["event_days"]))
    cutoff_day = local_day(cutoff, config["timezone"])
    removed = 0
    for path in paths.events_dir.glob("*.jsonl"):
        if path.stem < cutoff_day:
            path.unlink()
            removed += 1
    return removed


def backup_data(paths: FomorPaths, keep: int = 7) -> Path:
    stamp = utcnow().strftime("%Y%m%d%H%M%S")
    target = paths.backup_dir / f"fomor-{stamp}"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("config", "topics", "discoveries", "tombstones"):
        source = paths.root / name
        if source.exists():
            shutil.copytree(source, target / name, dirs_exist_ok=True)
    backups = sorted(path for path in paths.backup_dir.glob("fomor-*") if path.is_dir())
    for old in backups[:-keep]:
        shutil.rmtree(old, ignore_errors=True)
    return target
