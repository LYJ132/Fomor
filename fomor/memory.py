"""Memory runtime: topics, discoveries, feedback and lifecycle.

Short-lived Events live in :mod:`fomor.events`; this module owns the long-term
material that must survive Event cleanup.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import util
from .config import load_settings, paths
from .storage import FileLock, read_json, write_json

TOPIC_STATUSES = ("active", "dormant", "archived", "expired")

FEEDBACK_EFFECTS = {
    "interested": "提高该话题的后续探索优先级",
    "continue": "延续当前探索",
    "already_known": "更新该话题的认知状态",
    "not_interested": "记录明确的负向偏好",
    "irrelevant": "修正用户背景或当前问题理解",
    "applied": "记录实践进度和应用结果",
    "no_feedback": "暂时不作判断",
}


# --------------------------------------------------------------------------
# Topics
# --------------------------------------------------------------------------
def load_topics(root: str | Path | None = None) -> list[dict]:
    topics = []
    for path in sorted(paths(root)["topics"].glob("topic_*.json")):
        data = read_json(path)
        if data:
            topics.append(data)
    return topics


def save_topic(topic: dict, root: str | Path | None = None) -> None:
    path = paths(root)["topics"] / f"{topic['topic_id']}.json"
    with FileLock(path.with_suffix(".lock")):
        write_json(path, topic)


def find_topic(topic_id: str, root: str | Path | None = None) -> dict | None:
    if not topic_id:
        return None
    return read_json(paths(root)["topics"] / f"{topic_id}.json")


def create_topic(
    name: str,
    *,
    background: str,
    goal: str,
    root: str | Path | None = None,
) -> dict:
    topic = {
        "topic_id": util.new_id("topic"),
        "name": name,
        "background": background,
        "project": None,
        "user_goal": goal,
        "progress": [],
        "introduced_solutions": [],
        "known": [],
        "interests": [],
        "dislikes": [],
        "practices": [],
        "corrections": [],
        "evidence": [],
        "discovery_ids": [],
        "status": "active",
        "created_at": util.now_iso(),
        "last_activity_at": util.now_iso(),
    }
    save_topic(topic, root)
    return topic


def create_or_get_topic(
    cluster: dict,
    problem: dict,
    *,
    root: str | Path | None = None,
) -> dict:
    existing = find_topic(cluster.get("existing_topic_id") or "", root)
    if existing:
        return existing

    name = (cluster.get("name") or "未命名话题").strip()
    for topic in load_topics(root):
        if topic["name"].strip() == name:
            return topic

    return create_topic(
        name,
        background=cluster.get("summary") or problem.get("user_activity", ""),
        goal=problem.get("underlying_goal", ""),
        root=root,
    )


def attach_discovery(
    topic: dict,
    discovery: dict,
    problem: dict,
    root: str | Path | None = None,
) -> dict:
    if discovery["discovery_id"] not in topic["discovery_ids"]:
        topic["discovery_ids"].append(discovery["discovery_id"])
    topic["user_goal"] = problem.get("underlying_goal", topic.get("user_goal", ""))
    activity = problem.get("user_activity")
    if activity:
        topic["progress"].append({"at": util.now_iso(), "note": activity})
    for solution in [discovery.get("primary_solution")] + discovery.get("other_solutions", []):
        if solution and solution.get("name") not in topic["introduced_solutions"]:
            topic["introduced_solutions"].append(solution["name"])
    topic["last_activity_at"] = util.now_iso()
    if topic.get("status") in ("dormant", "archived"):
        topic["status"] = "active"
    save_topic(topic, root)
    return topic


# --------------------------------------------------------------------------
# Discoveries
# --------------------------------------------------------------------------
def save_discovery(discovery: dict, root: str | Path | None = None) -> None:
    path = paths(root)["discoveries"] / f"{discovery['discovery_id']}.json"
    with FileLock(path.with_suffix(".lock")):
        write_json(path, discovery)


def load_discoveries(root: str | Path | None = None) -> list[dict]:
    items = []
    for path in sorted(paths(root)["discoveries"].glob("discovery_*.json")):
        data = read_json(path)
        if data:
            items.append(data)
    items.sort(key=lambda d: d.get("created_at", ""))
    return items


def load_discovery(discovery_id: str, root: str | Path | None = None) -> dict | None:
    return read_json(paths(root)["discoveries"] / f"{discovery_id}.json")


# --------------------------------------------------------------------------
# Feedback
# --------------------------------------------------------------------------
def apply_feedback(
    discovery_id: str,
    action: str,
    note: str = "",
    root: str | Path | None = None,
) -> dict:
    if action not in FEEDBACK_EFFECTS:
        raise ValueError(f"unknown feedback action: {action}")
    discovery = load_discovery(discovery_id, root)
    if not discovery:
        raise ValueError(f"discovery not found: {discovery_id}")

    entry = {
        "action": action,
        "meaning": FEEDBACK_EFFECTS[action],
        "note": note,
        "at": util.now_iso(),
    }
    discovery.setdefault("feedback", []).append(entry)
    save_discovery(discovery, root)

    topic = find_topic(discovery.get("topic_id", ""), root)
    if topic:
        solution_names = [
            s.get("name", "")
            for s in [discovery.get("primary_solution")] + discovery.get("other_solutions", [])
            if s
        ]
        if action == "interested":
            topic["interests"].extend(n for n in solution_names if n not in topic["interests"])
            topic["progress"].append({"at": util.now_iso(), "note": "用户表示感兴趣"})
        elif action == "continue":
            topic["progress"].append({"at": util.now_iso(), "note": "用户要求继续深入"})
        elif action == "already_known":
            topic["known"].extend(n for n in solution_names if n not in topic["known"])
        elif action == "not_interested":
            topic["dislikes"].extend(n for n in solution_names if n not in topic["dislikes"])
        elif action == "irrelevant":
            topic["corrections"].append({"at": util.now_iso(), "note": note or "与当前场景不相关"})
        elif action == "applied":
            topic["practices"].append({"at": util.now_iso(), "solution": solution_names[0] if solution_names else "", "note": note})
        topic["feedback"] = topic.get("feedback", [])
        topic["feedback"].append({"discovery_id": discovery_id, **entry})
        topic["last_activity_at"] = util.now_iso()
        save_topic(topic, root)

    return {"discovery_id": discovery_id, "action": action, "effect": FEEDBACK_EFFECTS[action]}


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------
def lifecycle_sweep(root: str | Path | None = None) -> dict:
    settings = load_settings(root)
    dormant_days = settings["topic"]["dormant_days"]
    archive_days = settings["topic"]["archive_days"]
    now = util.now()
    changed = {"dormant": 0, "archived": 0, "reactivated": 0}

    for topic in load_topics(root):
        if topic.get("status") not in ("active", "dormant"):
            continue
        try:
            last = util.parse_iso(topic["last_activity_at"])
        except (KeyError, ValueError):
            continue
        idle_days = (now - last).days
        if topic["status"] == "active" and idle_days >= dormant_days:
            topic["status"] = "dormant"
            changed["dormant"] += 1
            save_topic(topic, root)
        elif topic["status"] == "dormant" and idle_days >= archive_days:
            topic["status"] = "archived"
            changed["archived"] += 1
            save_topic(topic, root)
    return changed
