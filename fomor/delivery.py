"""Static HTML delivery for discoveries (MVP: no server, no web app)."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .config import load_settings, paths
from . import memory, util

RELATIONSHIP_LABELS = {
    "alternative": "替代方案",
    "complementary": "互补方案",
    "evolutionary": "演进方案",
    "paradigm_shift": "范式变化",
}


def _list(items, empty: str = "—") -> str:
    if not items:
        return f'<p class="muted">{escape(empty)}</p>'
    lis = "".join(f"<li>{escape(str(item))}</li>" for item in items if item)
    return f"<ul>{lis}</ul>"


def _solution_block(solution: dict) -> str:
    if not solution:
        return ""
    label = RELATIONSHIP_LABELS.get(solution.get("relationship", ""), solution.get("relationship", ""))
    rows = [
        ("核心思路", escape(solution.get("core_idea", ""))),
        ("工作流程", escape(solution.get("workflow", ""))),
        ("所需组件", _chip_list(solution.get("components"))),
        ("主要优势", _list(solution.get("advantages"))),
        ("限制与代价", _list(solution.get("constraints"))),
        ("前置条件", _list(solution.get("requirements"))),
        ("适用场景", escape(solution.get("applicability", ""))),
    ]
    body = "".join(
        f'<div class="row"><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in rows
    )
    return (
        f'<div class="solution">'
        f'<div class="solution-head"><h3>{escape(solution.get("name", "未命名方案"))}</h3>'
        f'<span class="tag">{escape(label)}</span></div>{body}</div>'
    )


def _chip_list(items) -> str:
    if not items:
        return '<span class="muted">—</span>'
    return "".join(f'<span class="chip">{escape(str(i))}</span>' for i in items if i)


def _understanding(und: dict) -> str:
    approach = und.get("current_approach") or {}
    hypotheses = und.get("root_problem_hypotheses") or []
    hypo_html = "".join(
        f'<li><strong>{escape(h.get("hypothesis", ""))}</strong>'
        f'<span class="conf">置信度 {h.get("confidence", "?")}</span>'
        f'<div class="muted small">{escape("；".join(h.get("evidence", [])))}</div></li>'
        for h in hypotheses
    )
    return f"""
      <div class="grid2">
        <div><div class="label">用户正在做什么</div><p>{escape(und.get("user_activity", "—"))}</p></div>
        <div><div class="label">想实现什么</div><p>{escape(und.get("underlying_goal", "—"))}</p></div>
        <div><div class="label">当前采用的方式</div><p>{escape(approach.get("summary", "—"))}</p>
             <div>{_chip_list(approach.get("tools"))}</div></div>
        <div><div class="label">当前的阻碍</div>{_list(und.get("frictions"))}</div>
      </div>
      <div class="label">可能的根本问题（假设）</div>
      <ul class="hypotheses">{hypo_html or '<li class="muted">暂无</li>'}</ul>
      <div class="label">尚不确定</div>{_list(und.get("uncertainties"))}
    """


def _discovery_card(d: dict) -> str:
    score = d.get("score") or {}
    primary = d.get("primary_solution") or {}
    others = d.get("other_solutions") or []
    others_html = "".join(_solution_block(s) for s in others)
    return f"""
    <article class="card">
      <div class="meta">
        <span class="badge">{escape(d.get("topic_name", ""))}</span>
        <span class="muted small">{escape(d.get("created_at", ""))}</span>
        <span class="muted small">探索评分 {score.get("total", "—")} · {escape(score.get("decision", ""))}</span>
      </div>
      <h2>{escape(d.get("title", ""))}</h2>

      <section>
        <div class="label">我观察到了什么</div>
        <p>{escape(d.get("observed", ""))}</p>
      </section>

      <section>
        <div class="label">你可能在解决什么问题</div>
        {_understanding(d.get("problem_understanding") or {})}
      </section>

      <section>
        <div class="label">一个值得了解的新思路</div>
        {_solution_block(primary)}
      </section>

      {f'<section><div class="label">其他可选方案</div>{others_html}</section>' if others_html else ""}

      <section>
        <div class="label">与当前方式的区别</div>
        <p>{escape(d.get("comparison", ""))}</p>
      </section>

      <section>
        <div class="label">证据与延伸资料</div>
        {_list(d.get("evidence"))}
      </section>

      <footer class="feedback">
        反馈：fomor feedback {escape(d.get("discovery_id", ""))} --action
        interested | continue | already_known | not_interested | irrelevant | applied
      </footer>
    </article>
    """


def render_report(root: str | Path | None = None) -> Path:
    settings = load_settings(root)
    discoveries = sorted(memory.load_discoveries(root), key=lambda d: d.get("created_at", ""), reverse=True)
    topics = memory.load_topics(root)
    active_topics = [t for t in topics if t.get("status") == "active"]

    cards = "".join(_discovery_card(d) for d in discoveries)
    if not cards:
        cards = '<div class="empty">还没有探索结果。先用 <code>fomor collect</code> 记录一些问题，再运行 <code>fomor analyze</code>。</div>'

    topic_list = "".join(
        f'<li><span class="dot"></span>{escape(t.get("name", ""))}'
        f'<span class="muted small"> · {len(t.get("discovery_ids", []))} 次探索</span></li>'
        for t in active_topics
    )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fomor · 探索结果</title>
<style>
  :root {{
    --bg: #f6f5f1; --card: #ffffff; --ink: #1d1d1f; --muted: #86868b;
    --line: #e6e4de; --accent: #2f6b5f; --accent-soft: #e8f0ed;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    line-height: 1.7; }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 56px 24px 96px; }}
  header.top {{ margin-bottom: 40px; }}
  .brand {{ font-size: 13px; letter-spacing: .18em; text-transform: uppercase; color: var(--accent); }}
  h1 {{ font-size: 34px; line-height: 1.25; margin: 8px 0 12px; font-weight: 650; }}
  .sub {{ color: var(--muted); margin: 0; }}
  .stats {{ display: flex; gap: 28px; margin-top: 24px; flex-wrap: wrap; }}
  .stat b {{ font-size: 22px; display: block; }}
  .stat span {{ color: var(--muted); font-size: 13px; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 16px;
    padding: 30px 32px; margin-bottom: 28px; }}
  .meta {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }}
  .badge {{ background: var(--accent-soft); color: var(--accent); font-size: 12px;
    padding: 3px 10px; border-radius: 999px; }}
  h2 {{ font-size: 23px; margin: 6px 0 18px; line-height: 1.4; }}
  h3 {{ font-size: 17px; margin: 0; }}
  section {{ margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--line); }}
  .label {{ font-size: 12px; letter-spacing: .08em; color: var(--muted);
    text-transform: uppercase; margin-bottom: 8px; font-weight: 600; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 18px 28px; margin-bottom: 18px; }}
  p {{ margin: 0 0 6px; }}
  ul {{ margin: 4px 0 12px; padding-left: 20px; }}
  li {{ margin: 3px 0; }}
  .muted {{ color: var(--muted); }}
  .small {{ font-size: 12px; }}
  .solution {{ border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; margin-top: 12px; }}
  .solution-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }}
  .tag {{ font-size: 12px; color: var(--accent); border: 1px solid var(--accent); border-radius: 999px; padding: 2px 10px; }}
  .row {{ display: grid; grid-template-columns: 92px 1fr; gap: 10px; padding: 6px 0; }}
  .row .k {{ color: var(--muted); font-size: 13px; }}
  .chip {{ display: inline-block; background: var(--bg); border: 1px solid var(--line);
    border-radius: 6px; padding: 1px 8px; margin: 2px 4px 2px 0; font-size: 13px; }}
  .hypotheses li {{ margin-bottom: 8px; }}
  .conf {{ color: var(--accent); font-size: 12px; margin-left: 8px; }}
  .feedback {{ margin-top: 20px; padding-top: 14px; border-top: 1px dashed var(--line);
    color: var(--muted); font-size: 12px; font-family: ui-monospace, Menlo, monospace; }}
  .sidebar {{ margin-top: 40px; }}
  .sidebar ul {{ list-style: none; padding: 0; }}
  .sidebar li {{ padding: 6px 0; border-bottom: 1px solid var(--line); }}
  .dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent); margin-right: 8px; vertical-align: middle; }}
  .empty {{ background: var(--card); border: 1px dashed var(--line); border-radius: 16px;
    padding: 40px; text-align: center; color: var(--muted); }}
  code {{ background: var(--accent-soft); color: var(--accent); padding: 1px 6px; border-radius: 5px; }}
  footer.page {{ margin-top: 48px; color: var(--muted); font-size: 12px; text-align: center; }}
  @media (max-width: 640px) {{
    .grid2 {{ grid-template-columns: 1fr; }}
    .card {{ padding: 22px; }}
    h1 {{ font-size: 27px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">Fomor · Exploration Report</div>
    <h1>从日常问题中，发现另一种可能的解法</h1>
    <p class="sub">生成于 {escape(util.now_iso())} · 只展示经过理解与判断的探索结果</p>
    <div class="stats">
      <div class="stat"><b>{len(discoveries)}</b><span>探索结果</span></div>
      <div class="stat"><b>{len(topics)}</b><span>长期话题</span></div>
      <div class="stat"><b>{len(active_topics)}</b><span>活跃话题</span></div>
    </div>
  </header>

  {cards}

  {f'<aside class="sidebar"><div class="label">活跃话题</div><ul>{topic_list}</ul></aside>' if topic_list else ""}

  <footer class="page">Fomor MVP · 生成式探索结果不能替代你对该技术方案的独立判断</footer>
</div>
</body>
</html>
"""

    output = Path(settings.get("report", {}).get("output", "report.html"))
    if not output.is_absolute():
        output = paths(root)["root"] / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
