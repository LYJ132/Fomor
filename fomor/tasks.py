"""Background task bookkeeping (pending -> processing -> completed/failed)."""

from __future__ import annotations

from pathlib import Path

from . import util
from .config import paths
from .storage import FileLock, read_json, write_json


def _load(root=None) -> dict:
    return read_json(paths(root)["tasks"], {"tasks": []})


def start_task(task_type: str, payload: dict | None = None, root: str | Path | None = None) -> dict:
    path = paths(root)["tasks"]
    task = {
        "task_id": util.new_id("task"),
        "task_type": task_type,
        "status": "processing",
        "attempts": 1,
        "error": None,
        "payload": payload or {},
        "related": {},
        "created_at": util.now_iso(),
        "updated_at": util.now_iso(),
    }
    with FileLock(path.with_suffix(".lock")):
        data = _load(root)
        data["tasks"].append(task)
        write_json(path, data)
    return task


def finish_task(
    task_id: str,
    status: str = "completed",
    error: str | None = None,
    related: dict | None = None,
    root: str | Path | None = None,
) -> dict | None:
    path = paths(root)["tasks"]
    with FileLock(path.with_suffix(".lock")):
        data = _load(root)
        for task in data["tasks"]:
            if task["task_id"] == task_id:
                task["status"] = status
                task["error"] = error
                task["updated_at"] = util.now_iso()
                if related:
                    task["related"].update(related)
                write_json(path, data)
                return task
    return None


def list_tasks(root: str | Path | None = None) -> list[dict]:
    return _load(root)["tasks"]
