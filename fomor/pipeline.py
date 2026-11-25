"""The end-to-end analysis pipeline.

Order matters (PRD 2.6): aggregate -> understand -> decide whether it is worth
exploring -> only then generate directions / search solutions.
"""

from __future__ import annotations

from pathlib import Path

from . import events, llm as llm_mod, memory, tasks, util
from .config import load_settings
from .search import build_search

DIMENSION_KEYS = (
    "solution_space",
    "potential_gain",
    "cognitive_gain",
    "applicability",
    "necessity",
)


def _average_dimensions(dimensions: dict) -> float:
    values = [float(dimensions.get(key, 0) or 0) for key in DIMENSION_KEYS]
    return round(sum(values) / len(values), 2) if values else 0.0


def _decide(score: dict, settings: dict) -> tuple[str, float]:
    dimensions = score.get("dimensions", {})
    total = _average_dimensions(dimensions)
    if score.get("hard_stop"):
        return "none", total
    if total >= settings["scoring"]["explore_threshold"]:
        return "explore", total
    if total >= settings["scoring"]["watch_threshold"]:
        return "watch", total
    return "none", total


def _strip_event(event: dict) -> dict:
    return {
        "event_id": event["event_id"],
        "user_message": event["user_message"],
        "timestamp": event.get("timestamp"),
        "session_id": event.get("session_id"),
        "platform": event.get("platform"),
    }


def analyze(
    root: str | Path | None = None,
    *,
    lookback_days: int = 2,
    deliver: bool = True,
) -> dict:
    settings = load_settings(root)
    pending = events.pending_events(root, lookback_days=lookback_days)
    if not pending:
        return {"status": "empty", "message": "没有待分析的原始问题"}

    task = tasks.start_task("analysis", {"event_count": len(pending)}, root)
    try:
        model = llm_mod.build_llm(settings)
        search = build_search(settings)

        existing_topics = [
            {"topic_id": t["topic_id"], "name": t["name"], "user_goal": t.get("user_goal", "")}
            for t in memory.load_topics(root)
        ]
        clustering = model.complete_json(
            "aggregate",
            {"events": [_strip_event(e) for e in pending], "existing_topics": existing_topics},
        )

        discoveries: list[dict] = []
        skipped: list[dict] = []
        by_id = {e["event_id"]: e for e in pending}

        for cluster in clustering.get("clusters", []):
            cluster_events = [by_id[eid] for eid in cluster.get("event_ids", []) if eid in by_id]
            if not cluster_events:
                continue

            problem = model.complete_json(
                "understand",
                {"cluster": cluster, "events": [_strip_event(e) for e in cluster_events]},
            )
            score = model.complete_json(
                "score", {"problem": problem, "events": [_strip_event(e) for e in cluster_events]}
            )
            decision, total = _decide(score, settings)
            topic = memory.create_or_get_topic(cluster, problem, root=root)

            if decision != "explore":
                topic["progress"].append(
                    {
                        "at": util.now_iso(),
                        "note": f"本次判断为「{decision}」，暂不生成探索（评分 {total}）",
                    }
                )
                topic["last_activity_at"] = util.now_iso()
                memory.save_topic(topic, root)
                events.mark_analyzed([e["event_id"] for e in cluster_events], topic_id=topic["topic_id"], root=root)
                skipped.append({"topic": topic["name"], "decision": decision, "score": total})
                continue

            exploration = model.complete_json(
                "explore",
                {"problem": problem, "cluster": cluster, "events": [_strip_event(e) for e in cluster_events]},
            )
            solutions = exploration.get("solutions") or []
            if not solutions:
                skipped.append({"topic": topic["name"], "decision": "none", "score": total})
                events.mark_analyzed([e["event_id"] for e in cluster_events], topic_id=topic["topic_id"], root=root)
                continue

            search_results: list[dict] = []
            for direction in exploration.get("directions", [])[:2]:
                search_results.extend(search.search(direction, limit=3))

            meta = model.complete_json(
                "discovery",
                {
                    "problem": problem,
                    "primary_solution": solutions[0],
                    "other_solutions": solutions[1:],
                    "comparison": exploration.get("comparison", ""),
                },
            )

            evidence = []
            for solution in solutions:
                evidence.extend(solution.get("evidence", []))
            evidence.extend(r.get("url") or r.get("title", "") for r in search_results)

            discovery = {
                "discovery_id": util.new_id("discovery"),
                "topic_id": topic["topic_id"],
                "topic_name": topic["name"],
                "created_at": util.now_iso(),
                "title": meta.get("title") or f"关于「{topic['name']}」的一次探索",
                "observed": meta.get("observed", ""),
                "problem_understanding": problem,
                "score": {
                    "dimensions": score.get("dimensions", {}),
                    "total": total,
                    "decision": decision,
                    "rationale": score.get("rationale", ""),
                },
                "directions": exploration.get("directions", []),
                "primary_solution": solutions[0],
                "other_solutions": solutions[1:],
                "comparison": meta.get("comparison") or exploration.get("comparison", ""),
                "evidence": [item for item in evidence if item],
                "feedback": [],
            }
            memory.save_discovery(discovery, root)
            memory.attach_discovery(topic, discovery, problem, root)
            events.mark_analyzed([e["event_id"] for e in cluster_events], topic_id=topic["topic_id"], root=root)
            discoveries.append(discovery)

        tasks.finish_task(
            task["task_id"],
            related={"discoveries": [d["discovery_id"] for d in discoveries]},
            root=root,
        )
        cleanup = events.cleanup_expired(root)

        report_path = None
        if deliver:
            from .delivery import render_report

            report_path = str(render_report(root))

        return {
            "status": "ok",
            "analyzed_events": len(pending),
            "discoveries": [
                {"discovery_id": d["discovery_id"], "title": d["title"], "topic": d["topic_name"]}
                for d in discoveries
            ],
            "skipped": skipped,
            "cleanup": cleanup,
            "report": report_path,
        }
    except Exception as exc:  # noqa: BLE001 - recorded then re-raised
        tasks.finish_task(task["task_id"], status="failed", error=str(exc), root=root)
        raise
