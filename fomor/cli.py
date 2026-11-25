"""Command line entry point for Fomor."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__, config, events, memory, scheduler, tasks, util
from .delivery import render_report
from .pipeline import analyze as run_analysis


def _setup_logging(root=None) -> None:
    p = config.ensure_dirs(root)
    handler = logging.FileHandler(p["logs"] / "fomor.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root_logger = logging.getLogger("fomor")
    root_logger.setLevel(logging.INFO)
    if not root_logger.handlers:
        root_logger.addHandler(handler)


def _print(data) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_init(args) -> int:
    p = config.ensure_dirs(args.root)
    config.save_settings(config.DEFAULT_SETTINGS, args.root)
    print(f"Fomor 已初始化：{p['root']}")
    print(f"配置文件：{p['settings']}")
    print("默认使用 Mock 模型；如需真实模型，请修改 settings.json 并将 llm.mock 设为 false。")
    return 0


def cmd_collect(args) -> int:
    event = events.record_event(
        args.message,
        platform=args.platform,
        session_id=args.session_id,
        timestamp=args.timestamp,
        root=args.root,
    )
    print(f"已记录事件 {event['event_id']}（{event['timestamp']}）")
    return 0


def cmd_import(args) -> int:
    raw = sys.stdin.read() if args.path in ("-", "") else Path(args.path).read_text(encoding="utf-8")
    items = json.loads(raw)
    if isinstance(items, dict):
        items = items.get("events", [])
    created = events.import_events(items, root=args.root)
    print(f"已导入 {len(created)} 条事件")
    return 0


def cmd_hook(args) -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print("hook 需要从 stdin 读取 JSON", file=sys.stderr)
        return 2
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"hook 输入不是合法 JSON: {exc}", file=sys.stderr)
        return 2

    message = payload.get("user_message") or payload.get("message") or payload.get("prompt")
    if not message:
        print("hook 输入缺少 user_message / message / prompt 字段", file=sys.stderr)
        return 2

    event = events.record_event(
        message,
        platform=payload.get("platform") or args.platform,
        session_id=payload.get("session_id"),
        timestamp=payload.get("timestamp"),
        event_id=payload.get("event_id"),
        root=args.root,
    )
    print(f"已记录事件 {event['event_id']}")
    return 0


def cmd_analyze(args) -> int:
    result = run_analysis(args.root, lookback_days=args.lookback_days, deliver=not args.no_report)
    _print(result)
    return 0


def cmd_run(args) -> int:
    _setup_logging(args.root)
    if args.once:
        result = scheduler.run_due(args.root)
        _print(result or {"status": "not_due"})
        return 0
    scheduler.run_forever(args.root, interval=args.interval)
    return 0


def cmd_list(args) -> int:
    if args.what == "topics":
        items = [
            {
                "topic_id": t["topic_id"],
                "name": t["name"],
                "status": t.get("status"),
                "goal": t.get("user_goal"),
                "discoveries": len(t.get("discovery_ids", [])),
                "last_activity_at": t.get("last_activity_at"),
            }
            for t in memory.load_topics(args.root)
        ]
    elif args.what == "tasks":
        items = tasks.list_tasks(args.root)
    else:
        items = [
            {
                "discovery_id": d["discovery_id"],
                "title": d["title"],
                "topic": d.get("topic_name"),
                "created_at": d["created_at"],
                "feedback": len(d.get("feedback", [])),
            }
            for d in memory.load_discoveries(args.root)
        ]
    _print(items)
    return 0


def cmd_show(args) -> int:
    discovery = memory.load_discovery(args.discovery_id, args.root)
    if not discovery:
        print(f"未找到探索结果：{args.discovery_id}", file=sys.stderr)
        return 1
    _print(discovery)
    return 0


def cmd_feedback(args) -> int:
    result = memory.apply_feedback(args.discovery_id, args.action, note=args.note, root=args.root)
    _print(result)
    return 0


def cmd_cleanup(args) -> int:
    result = events.cleanup_expired(args.root, retention_hours=args.retention_hours)
    _print(result)
    return 0


def cmd_report(args) -> int:
    path = render_report(args.root)
    print(f"报告已生成：{path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fomor", description="Fomor · AI 探索助手")
    parser.add_argument("--version", action="version", version=f"fomor {__version__}")
    parser.add_argument("--root", default=None, help="数据目录（默认 FOMOR_HOME 或 ./data）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="初始化数据目录与默认配置")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("collect", help="记录一条用户问题")
    p.add_argument("message", help="用户问题内容")
    p.add_argument("--platform", default="manual")
    p.add_argument("--session-id", default=None)
    p.add_argument("--timestamp", default=None)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("import", help="从 JSON 文件或 stdin 导入事件")
    p.add_argument("path", nargs="?", default="-", help="JSON 文件路径，- 表示 stdin")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("hook", help="Hook 入口：从 stdin 读取 JSON 并记录事件")
    p.add_argument("--platform", default="trae")
    p.set_defaults(func=cmd_hook)

    p = sub.add_parser("analyze", help="立即运行一次分析")
    p.add_argument("--lookback-days", type=int, default=2)
    p.add_argument("--no-report", action="store_true", help="不生成 HTML 报告")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("run", help="启动后台调度器")
    p.add_argument("--interval", type=int, default=300, help="轮询间隔秒数")
    p.add_argument("--once", action="store_true", help="只检查一次是否到期")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("list", help="列出探索结果 / 话题 / 任务")
    p.add_argument("what", nargs="?", choices=["discoveries", "topics", "tasks"], default="discoveries")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="查看一条探索结果")
    p.add_argument("discovery_id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("feedback", help="提交对探索结果的反馈")
    p.add_argument("discovery_id")
    p.add_argument(
        "--action",
        required=True,
        choices=["interested", "continue", "already_known", "not_interested", "irrelevant", "applied", "no_feedback"],
    )
    p.add_argument("--note", default="")
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("cleanup", help="清理过期原始事件")
    p.add_argument("--retention-hours", type=int, default=None)
    p.set_defaults(func=cmd_cleanup)

    p = sub.add_parser("report", help="根据已有数据重新生成 HTML 报告")
    p.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.root)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - surface a clean CLI error
        logging.getLogger("fomor").exception("command failed")
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
