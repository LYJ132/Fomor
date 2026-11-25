"""LLM access layer.

The MVP defaults to a deterministic :class:`MockLLM` so the whole pipeline can
run offline.  Setting ``llm.mock = false`` and exporting the configured API key
switches to any OpenAI-compatible ``/chat/completions`` endpoint.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

from . import prompts, util


class LLMError(RuntimeError):
    pass


class MockLLM:
    """Deterministic, offline stand-in used for demos and tests."""

    name = "mock"

    def complete_json(self, task: str, payload: dict) -> dict:
        handler = getattr(self, f"_{task}", None)
        if handler is None:
            raise LLMError(f"mock does not implement task: {task}")
        return handler(payload)

    # -- tasks -----------------------------------------------------------
    def _aggregate(self, payload: dict) -> dict:
        events = payload.get("events", [])
        if not events:
            return {"clusters": []}
        messages = [e["user_message"] for e in events]
        domain, _, _, _ = _infer_domain(messages)
        name = {
            "数据服务": "本地与云端数据服务架构",
            "Agent 工程": "Agent 执行与工作流",
            "交互设计": "Agent 交互方式设计",
        }.get(domain, util.truncate(messages[0], 18))
        return {
            "clusters": [
                {
                    "cluster_id": util.new_id("clu"),
                    "name": name,
                    "summary": f"{len(events)} 个问题可能围绕同一个探索主题",
                    "event_ids": [e["event_id"] for e in events],
                    "existing_topic_id": None,
                }
            ]
        }

    def _understand(self, payload: dict) -> dict:
        events = payload.get("events", [])
        messages = [e["user_message"] for e in events]
        domain, goal, frictions, root = _infer_domain(messages)
        tools = _infer_tools(messages)
        return {
            "observed_questions": messages,
            "user_activity": f"围绕「{util.truncate(goal, 24)}」持续推进相关工作",
            "underlying_goal": goal,
            "current_approach": {
                "summary": "在现有技术栈内逐项解决问题，尚未整体设计解决路径",
                "tools": tools,
            },
            "frictions": frictions,
            "root_problem_hypotheses": [
                {
                    "hypothesis": root,
                    "confidence": 0.45,
                    "evidence": messages[:2],
                }
            ],
            "uncertainties": [
                "Mock 模式未读取会话上下文，结论仅用于验证链路",
                f"仍需确认：{domain}场景下哪些约束是硬性要求",
            ],
        }

    def _score(self, payload: dict) -> dict:
        return {
            "dimensions": {
                "solution_space": 4,
                "potential_gain": 4,
                "cognitive_gain": 4,
                "applicability": 4,
                "necessity": 4,
            },
            "hard_stop": False,
            "rationale": "问题涉及多个可替代路径，且与用户当前场景直接相关（Mock 评分）。",
        }

    def _explore(self, payload: dict) -> dict:
        problem = payload.get("problem", {})
        goal = problem.get("underlying_goal") or "当前目标"
        frictions = problem.get("frictions") or ["当前方式在复杂度上升后可能难以扩展"]
        evidence = ["Mock 示例：接入真实搜索后应补充可访问的资料链接"]
        solutions = [
            {
                "name": "职责分层：把变化快的部分与稳定的部分解耦",
                "core_idea": f"围绕「{goal}」重新划分职责边界，让每一层只负责一件事。",
                "workflow": "识别职责 → 拆分边界 → 定义接口 → 分别部署与演进",
                "components": ["本地服务", "云端基础设施", "任务队列或消息通道"],
                "advantages": ["边界清晰，便于独立演进", "降低单点复杂度"],
                "constraints": ["前期需要额外的接口设计", "跨层排障成本上升"],
                "requirements": ["明确各层职责", "具备基本的部署与监控能力"],
                "applicability": "系统开始变复杂、且多种职责混杂在同一个服务中时",
                "relationship": "alternative",
                "evidence": evidence,
            },
            {
                "name": "在现有方案上补齐可观测性与失败恢复",
                "core_idea": "不改变整体架构，只补上当前最痛的短板。",
                "workflow": "定位主要失败点 → 增加状态记录 → 增加重试与告警",
                "components": ["日志", "任务状态存储", "告警渠道"],
                "advantages": ["迁移成本低", "能快速改善稳定性"],
                "constraints": ["不解决结构性问题", "复杂度继续上升时仍需重构"],
                "requirements": ["可以接受在当前方案上继续投入"],
                "applicability": "当前方案整体可用、只是局部不稳定时",
                "relationship": "complementary",
                "evidence": evidence,
            },
            {
                "name": "演进为可恢复的工作流",
                "core_idea": "把一次性执行改造成有状态、可恢复、可重放的工作流。",
                "workflow": "定义状态机 → 持久化执行状态 → 失败后从断点恢复",
                "components": ["持久化工作流引擎或任务队列", "状态存储", "调度器"],
                "advantages": ["支持长任务与失败恢复", "执行过程可审计"],
                "constraints": ["引入新的运行时依赖", "需要重新设计任务模型"],
                "requirements": ["任务会长期运行或涉及人工介入"],
                "applicability": "任务开始出现复杂状态、失败恢复和人工介入需求时",
                "relationship": "evolutionary",
                "evidence": evidence,
            },
        ]
        return {
            "directions": [
                f"优化「{util.truncate(frictions[0], 24)}」这一瓶颈",
                "换一种职责划分方式，而不是继续在现有结构内优化",
                "把一次性执行演进为可恢复、可观测的流程",
            ],
            "solutions": solutions,
            "comparison": (
                "复杂度较低时，继续演进现有方案更划算；"
                f"当「{util.truncate(goal, 20)}」成为长期目标时，"
                "职责分层或可恢复工作流更值得投入。"
            ),
        }

    def _discovery(self, payload: dict) -> dict:
        problem = payload.get("problem", {})
        goal = problem.get("underlying_goal") or "当前目标"
        questions = problem.get("observed_questions") or []
        observed = "你近期连续提出了这些问题：" + "；".join(questions) + f"。它们可能共同指向：{goal}。"
        return {
            "title": f"当「{util.truncate(goal, 22)}」开始变复杂，你可能需要的不只是一个工具",
            "observed": observed,
            "comparison": payload.get("comparison", ""),
        }


class OpenAICompatLLM:
    """Minimal client for OpenAI-compatible chat completion endpoints."""

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.3,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def complete_json(self, task: str, payload: dict) -> dict:
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": prompts.build_messages(task, payload),
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM request failed: {exc.reason}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"unexpected LLM response: {data}") from exc
        return _parse_json(content)


def _parse_json(content: str) -> dict:
    text = content.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM did not return valid JSON: {content[:200]}") from exc


def _infer_domain(messages: list[str]) -> tuple[str, str, list[str], str]:
    text = " ".join(messages).lower()
    if any(k in text for k in ("docker", "supabase", "数据库", "数据采集", "本地服务")):
        return (
            "数据服务",
            "构建稳定、易维护、可连接云端的数据服务架构",
            ["本地与云端的职责边界尚未明确", "服务部署与运维成本较高"],
            "哪些职责应由本地服务承担、哪些交给云端基础设施，尚未形成清晰边界",
        )
    if any(k in text for k in ("hook", "agent", "subagent", "工作流", "任务", "调度")):
        return (
            "Agent 工程",
            "建立可靠的 Agent 执行与工作流体系",
            ["任务状态与失败恢复缺少统一机制", "跨会话、跨任务的上下文难以保持"],
            "当前执行机制缺少可恢复的任务状态与统一调度",
        )
    if any(k in text for k in ("交互", "画布", "笔", "键盘", "鼠标", "界面")):
        return (
            "交互设计",
            "设计更自然的 Agent 交互方式",
            ["现有办公交互范式限制了表达方式"],
            "交互方式仍沿用桌面办公范式，未针对 Agent 协作重新设计",
        )
    return (
        "通用",
        "推进当前工作目标",
        ["当前方式在复杂度上升后可能难以扩展"],
        "当前解决方式可能限制了整体方案的选择空间",
    )


def _infer_tools(messages: list[str]) -> list[str]:
    text = " ".join(messages).lower()
    known = {
        "docker": "Docker",
        "supabase": "Supabase",
        "cron": "Cron",
        "hook": "Hook",
        "agent": "Agent",
        "redis": "Redis",
        "postgres": "PostgreSQL",
        "python": "Python",
        "typescript": "TypeScript",
    }
    return [label for key, label in known.items() if key in text]


def build_llm(settings: dict):
    cfg = settings.get("llm", {})
    if cfg.get("mock", True):
        return MockLLM()
    api_key = os.environ.get(cfg.get("api_key_env", "FOMOR_LLM_API_KEY"), "").strip()
    if not api_key:
        raise LLMError(
            f"missing API key: set {cfg.get('api_key_env', 'FOMOR_LLM_API_KEY')} "
            "or enable llm.mock in settings.json"
        )
    return OpenAICompatLLM(
        base_url=cfg.get("base_url", "https://api.openai.com/v1"),
        api_key=api_key,
        model=cfg.get("model", "gpt-4o-mini"),
        temperature=cfg.get("temperature", 0.3),
        timeout=cfg.get("timeout", 120),
    )
