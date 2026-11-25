"""Next-day implicit feedback: look back at prompts inside the observation window."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .paths import FomorPaths
from .store import (
    Discovery,
    append_event,
    list_discoveries,
    load_topic,
    promote_discovery,
    expire_discovery,
    save_discovery,
    save_topic,
)
from .utils import new_id, parse_iso, similarity, to_iso, utcnow

NEGATIVE_MARKERS = ("已经了解", "我知道了", "不感兴趣", "不相关", "不需要", "用不上")
STRONG_MARKERS = ("继续深入", "详细说说", "想试试", "怎么落地", "具体怎么做", "还能怎么做")


def _discovery_text(discovery: Discovery) -> str:
    parts = [str(discovery.get("topic_name") or ""), str(discovery.get("title") or "")]
    for solution in [discovery.get("primary_solution"), *discovery.get("other_solutions", [])]:
        if solution:
            parts.append(str(solution.get("name") or ""))
            parts.append(str(solution.get("core_idea") or ""))
    return " ".join(parts)


def _ensure_topic(paths: FomorPaths, discovery: Discovery) -> dict[str, Any]:
    topic = load_topic(paths, discovery["topic_id"])
    if topic:
        return topic
    now = to_iso(utcnow())
    topic = {
        "topic_id": discovery["topic_id"],
        "name": discovery.get("topic_name") or "未命名主题",
        "background": "由反馈回看补建的话题记录",
        "project": None,
        "user_goal": (discovery.get("problem_understanding") or {}).get("goal"),
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
        "created_at": now,
        "last_activity_at": now,
        "feedback": [],
    }
    return topic


def classify(discovery: Discovery, events: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    """Heuristic attribution used by the offline skeleton."""
    discovery_text = _discovery_text(discovery)
    topic_name = str(discovery.get("topic_name") or "")
    best = {"signal": "none", "confidence": 0.0, "event_id": None, "score": 0.0, "reason": ""}
    for event in events:
        message = str(event.get("user_message") or "")
        if not message:
            continue
        if any(marker in message for marker in NEGATIVE_MARKERS) and topic_name and topic_name in message:
            return {
                "signal": "negative",
                "confidence": 0.7,
                "event_id": event["event_id"],
                "score": 1.0,
                "reason": "用户明确表示已了解或不感兴趣",
            }
        if any(marker in message for marker in STRONG_MARKERS) and similarity(discovery_text, message) >= float(
            config["feedback"]["weak_similarity"]
        ):
            return {
                "signal": "strong",
                "confidence": 0.8,
                "event_id": event["event_id"],
                "score": 1.0,
                "reason": "用户明确要求继续深入或尝试",
            }
        score = similarity(discovery_text, message)
        if topic_name and len(topic_name) >= 4 and topic_name in message:
            score = max(score, 0.3)
        if score > best["score"]:
            best = {
                "signal": "none",
                "confidence": 0.0,
                "event_id": event["event_id"],
                "score": score,
                "reason": "",
            }
    strong = float(config["feedback"]["strong_similarity"])
    weak = float(config["feedback"]["weak_similarity"])
    if best["score"] >= strong:
        best.update(signal="strong", confidence=min(0.9, 0.5 + best["score"]), reason="再次提到同一方案或主题")
    elif best["score"] >= weak:
        best.update(signal="weak", confidence=0.4, reason="询问同一主题下的相邻问题")
    return best


def evaluate_feedback(
    paths: FomorPaths,
    config: dict[str, Any],
    events: list[dict[str, Any]],
    run_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Promote discoveries with interest, expire stale ones. Feedback first."""
    moment = now or utcnow()
    promoted, dismissed, expired, evaluated = [], [], [], []
    for discovery in list_discoveries(paths, status="observing"):
        delivered = parse_iso(discovery["created_at"])
        if delivered >= moment:
            continue
        window_events = [
            event
            for event in events
            if delivered <= parse_iso(event["timestamp"]) < moment
            and event.get("event_id") not in discovery.get("feedback_event_ids", [])
        ]
        result = classify(discovery, window_events, config)
        discovery["last_evaluated_run_id"] = run_id
        discovery["last_evaluated_at"] = to_iso(moment)
        evaluated.append(discovery["discovery_id"])

        if result["signal"] in ("strong", "weak"):
            topic = _ensure_topic(paths, discovery)
            topic.setdefault("interests", []).append(
                {
                    "discovery_id": discovery["discovery_id"],
                    "signal": result["signal"],
                    "confidence": result["confidence"],
                    "evidence_event_ids": [result["event_id"]] if result["event_id"] else [],
                    "at": to_iso(moment),
                }
            )
            topic.setdefault("evidence", []).extend(
                event_id for event_id in [result["event_id"]] if event_id and event_id not in topic["evidence"]
            )
            if discovery["topic_id"] not in topic.get("discovery_ids", []):
                topic.setdefault("discovery_ids", []).append(discovery["discovery_id"])
            topic["last_activity_at"] = to_iso(moment)
            save_topic(paths, topic)
            discovery["feedback"] = result
            promote_discovery(paths, discovery)
            promoted.append(discovery["discovery_id"])
            continue

        if result["signal"] == "negative":
            topic = _ensure_topic(paths, discovery)
            topic.setdefault("dislikes", []).append(
                {"discovery_id": discovery["discovery_id"], "reason": result["reason"], "at": to_iso(moment)}
            )
            topic["last_activity_at"] = to_iso(moment)
            save_topic(paths, topic)
            discovery["feedback"] = result
            discovery["status"] = "dismissed"
            save_discovery(paths, discovery)
            pending = paths.pending_dir / f"{discovery['discovery_id']}.json"
            if pending.exists():
                pending.unlink()
            dismissed.append(discovery["discovery_id"])
            continue

        if moment >= parse_iso(discovery["expires_at"]):
            expire_discovery(paths, discovery, config)
            expired.append(discovery["discovery_id"])
        else:
            save_discovery(paths, discovery)

    return {
        "evaluated": evaluated,
        "promoted": promoted,
        "dismissed": dismissed,
        "expired": expired,
    }
