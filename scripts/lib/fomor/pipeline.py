"""Minimal analysis pipeline: feedback first, then aggregate/understand/explore."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .config import load_config
from .feedback import evaluate_feedback
from .llm import BaseLLM, build_llm
from .paths import FomorPaths
from .scheduler import is_due, next_cutoff
from .store import (
    append_run,
    backup_data,
    cleanup_events,
    list_discoveries,
    list_topics,
    load_state,
    mark_events_analyzed,
    save_discovery,
    save_state,
    save_topic,
    iter_events,
)
from .utils import file_lock, local_day, new_id, normalize_text, parse_iso, to_iso, utcnow


def _window_start(paths: FomorPaths, state: dict[str, Any], now: datetime) -> datetime:
    last = state.get("last_success_at")
    if last:
        return parse_iso(last)
    pending = list_discoveries(paths, status="observing")
    if pending:
        return min(parse_iso(item["created_at"]) for item in pending)
    return now - timedelta(hours=24)


def _find_topic(paths: FomorPaths, name: str) -> dict[str, Any] | None:
    wanted = normalize_text(name)
    for topic in list_topics(paths):
        if normalize_text(topic.get("name", "")) == wanted:
            return topic
    return None


def _upsert_topic(
    paths: FomorPaths,
    cluster: dict[str, Any],
    understanding: dict[str, Any],
    at: str,
) -> dict[str, Any]:
    topic = _find_topic(paths, cluster["name"])
    if topic is None:
        topic = {
            "topic_id": new_id("topic"),
            "name": cluster["name"],
            "background": cluster.get("summary", ""),
            "project": None,
            "user_goal": understanding.get("goal"),
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
            "created_at": at,
            "last_activity_at": at,
            "feedback": [],
        }
    topic["user_goal"] = understanding.get("goal") or topic.get("user_goal")
    topic.setdefault("progress", []).append(
        {"at": at, "note": understanding.get("activity") or "继续推进相关工作"}
    )
    topic["last_activity_at"] = at
    return topic


def _assemble_discovery(
    topic: dict[str, Any],
    cluster: dict[str, Any],
    understanding: dict[str, Any],
    score: dict[str, Any],
    exploration: dict[str, Any],
    rendered: dict[str, Any],
    config: dict[str, Any],
    now,
) -> dict[str, Any]:
    solutions = exploration.get("solutions") or []
    primary = solutions[0] if solutions else {}
    others = solutions[1:]
    discovery_id = new_id("discovery")
    created = to_iso(now)
    return {
        "discovery_id": discovery_id,
        "topic_id": topic["topic_id"],
        "topic_name": topic["name"],
        "created_at": created,
        "status": "observing",
        "feedback_due_at": to_iso(next_cutoff(now, config)),
        "expires_at": to_iso(now + timedelta(days=int(config["retention"]["feedback_days"]))),
        "title": rendered.get("title") or f"关于「{topic['name']}」的另一条路径",
        "observed": rendered.get("observed") or cluster.get("summary", ""),
        "problem_understanding": understanding,
        "score": score,
        "directions": exploration.get("directions", []),
        "primary_solution": primary,
        "other_solutions": others,
        "comparison": rendered.get("comparison", ""),
        "closing_question": rendered.get("closing_question", ""),
        "evidence": exploration.get("evidence") or rendered.get("evidence", []),
        "confidence_notes": rendered.get("confidence_notes", ""),
        "search_queries": exploration.get("search_queries", []),
        "feedback": {"signal": "none", "confidence": 0.0, "reason": ""},
        "feedback_event_ids": [],
        "source_event_ids": cluster.get("event_ids", []),
    }


def _render_report(paths: FomorPaths, config: dict[str, Any], now, feedback: dict, discoveries: list[dict], skipped: str | None) -> str:
    day = local_day(now, config["timezone"])
    lines = [f"# Fomor 探索报告 · {day}", ""]
    lines.append("## 反馈回看")
    if not feedback["evaluated"]:
        lines.append("今天没有待回看的探索结果。")
    else:
        lines.append(
            f"评估 {len(feedback['evaluated'])} 条；"
            f"移入长期记忆 {len(feedback['promoted'])} 条；"
            f"明确不感兴趣 {len(feedback['dismissed'])} 条；"
            f"过期 {len(feedback['expired'])} 条。"
        )
    lines.append("")
    lines.append("## 本次新发现")
    if skipped:
        lines.append(skipped)
    elif not discoveries:
        lines.append("本次没有发现值得探索的新方向，不做硬推。")
    for discovery in discoveries:
        lines.append("")
        lines.append(f"### {discovery['title']}")
        lines.append("")
        lines.append(discovery.get("observed", ""))
        lines.append("")
        understanding = discovery.get("problem_understanding", {})
        lines.append(f"**可能在解决**：{understanding.get('goal') or 'unknown'}")
        lines.append("")
        lines.append(f"**当前方式**：{understanding.get('current_approach') or 'unknown'}")
        lines.append("")
        lines.append(f"**主要阻碍**：{'；'.join(understanding.get('frictions') or []) or 'unknown'}")
        lines.append("")
        primary = discovery.get("primary_solution") or {}
        if primary:
            lines.append(f"**一条值得了解的新思路：{primary.get('name', '')}**")
            lines.append("")
            lines.append(primary.get("core_idea", ""))
            lines.append("")
            lines.append(f"流程：{primary.get('workflow', '')}")
            lines.append("")
            lines.append(f"限制：{'；'.join(primary.get('constraints') or [])}")
        others = discovery.get("other_solutions") or []
        if others:
            lines.append("")
            lines.append("**其他可选方案**")
            for solution in others:
                lines.append(
                    f"- {solution.get('name')}（{solution.get('relationship', 'unknown')}）："
                    f"{solution.get('core_idea', '')}"
                )
        if discovery.get("comparison"):
            lines.append("")
            lines.append(f"**与当前方式的区别**：{discovery['comparison']}")
        if discovery.get("closing_question"):
            lines.append("")
            lines.append(f"**留给你判断**：{discovery['closing_question']}")
    lines.append("")
    lines.append("---")
    lines.append("如果这条探索对你有用，直接继续追问即可；没有追问的内容会在到期后自动删除。")
    text = "\n".join(lines) + "\n"
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    (paths.reports_dir / f"{day}.md").write_text(text, encoding="utf-8")
    (paths.reports_dir / "latest.md").write_text(text, encoding="utf-8")
    return text


def run_analysis(
    paths: FomorPaths,
    config: dict[str, Any] | None = None,
    llm: BaseLLM | None = None,
    now=None,
    scheduled: bool = False,
    make_backup: bool = True,
) -> dict[str, Any]:
    config = config or load_config(paths)
    moment = now or utcnow()
    paths.ensure()
    with file_lock(paths.lock_file):
        if scheduled and not is_due(paths, config, moment):
            return {
                "status": "skipped",
                "reason": "not_due",
                "report": "还没到下一次 03:00，且已有成功运行记录。",
            }
        state = load_state(paths)
        run_id = new_id("run")
        started = to_iso(moment)
        window_start = _window_start(paths, state, moment)
        recent_events = sorted(iter_events(paths, since=window_start, until=moment), key=lambda e: e["timestamp"])
        feedback_events = sorted(
            iter_events(
                paths,
                since=min(
                    [parse_iso(item["created_at"]) for item in list_discoveries(paths, status="observing")]
                    or [window_start]
                ),
                until=moment,
            ),
            key=lambda e: e["timestamp"],
        )
        feedback = evaluate_feedback(paths, config, feedback_events, run_id, moment)

        new_events = [
            event
            for event in recent_events
            if not event.get("analyzed_at")
        ][: int(config["analysis"]["max_events_per_run"])]
        skipped = None
        discoveries: list[dict[str, Any]] = []
        provider = llm or build_llm(config)

        if len(new_events) < int(config["analysis"]["min_events_for_discovery"]):
            skipped = "本次没有新的用户问题，暂不生成探索。"
        else:
            try:
                aggregated = provider.json("aggregate", {"date": local_day(moment, config["timezone"]), "events": new_events})
                clusters = aggregated.get("topics", [])[: int(config["analysis"]["max_topics_per_run"])]
                by_id = {event["event_id"]: event for event in new_events}
                for cluster in clusters:
                    events = [by_id[event_id] for event_id in cluster.get("event_ids", []) if event_id in by_id]
                    if not events:
                        events = new_events
                    understanding = provider.json(
                        "understand",
                        {"topic_name": cluster["name"], "events": events},
                    )
                    score = provider.json(
                        "opportunity",
                        {"topic_name": cluster["name"], "understanding": understanding},
                    )
                    decision = score.get("decision", "none")
                    total = float(score.get("total", 0))
                    if decision == "explore" and total < float(config["scoring"]["explore_threshold"]):
                        decision = "watch"
                    at = to_iso(moment)
                    if decision != "explore":
                        continue
                    exploration = provider.json(
                        "explore",
                        {"topic_name": cluster["name"], "understanding": understanding, "score": score},
                    )
                    rendered = provider.json(
                        "discovery",
                        {
                            "topic_name": cluster["name"],
                            "events": events,
                            "understanding": understanding,
                            "score": score,
                            "exploration": exploration,
                        },
                    )
                    # Create the topic first, then attach the finalized discovery.
                    topic = _upsert_topic(paths, cluster, understanding, at)
                    discovery = _assemble_discovery(
                        topic, cluster, understanding, score, exploration, rendered, config, moment
                    )
                    topic.setdefault("discovery_ids", []).append(discovery["discovery_id"])
                    for solution in [discovery.get("primary_solution"), *discovery.get("other_solutions", [])]:
                        if solution and solution.get("name") not in topic.setdefault("introduced_solutions", []):
                            topic["introduced_solutions"].append(solution["name"])
                    save_topic(paths, topic)
                    save_discovery(paths, discovery)
                    mark_events_analyzed(paths, events, topic["topic_id"], moment)
                    discoveries.append(discovery)
            except Exception as error:  # keep a readable failure record for the skeleton
                skipped = f"分析失败：{error}"

        report = _render_report(paths, config, moment, feedback, discoveries, skipped)
        finished = to_iso(utcnow())
        failed = bool(skipped and skipped.startswith("分析失败"))
        status = "failed" if failed else "completed"
        append_run(
            paths,
            {
                "run_id": run_id,
                "run_type": "scheduled" if scheduled else "manual",
                "status": status,
                "started_at": started,
                "finished_at": finished,
                "window_start": to_iso(window_start),
                "window_end": to_iso(moment),
                "feedback": feedback,
                "discovery_ids": [item["discovery_id"] for item in discoveries],
                "event_count": len(new_events),
                "error": skipped if status == "failed" else None,
            },
        )
        state.update(
            {
                "last_attempt_at": started,
                "last_run_id": run_id,
                "last_event_count": len(new_events),
            }
        )
        if status == "completed":
            state["last_success_at"] = started
            save_state(paths, state)
        else:
            save_state(paths, state)
        if make_backup:
            backup_data(paths)
        cleanup_events(paths, config)
        return {
            "status": status,
            "run_id": run_id,
            "feedback": feedback,
            "discoveries": [item["discovery_id"] for item in discoveries],
            "report": report,
            "skipped": skipped,
        }
