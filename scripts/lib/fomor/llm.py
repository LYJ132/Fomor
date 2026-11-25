"""Model providers.

The skeleton ships with a deterministic mock provider so the whole pipeline
can run offline.  ``traecli`` uses the local Trae CLI in non-interactive mode;
``openai`` talks to any OpenAI-compatible endpoint.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from .prompts import build_prompt
from .utils import extract_json


class LLMError(RuntimeError):
    pass


class BaseLLM:
    def complete(self, task: str, variables: dict[str, Any]) -> str:
        raise NotImplementedError

    def json(self, task: str, variables: dict[str, Any]) -> Any:
        return extract_json(self.complete(task, variables))


class MockLLM(BaseLLM):
    """Deterministic output that keeps the pipeline runnable without a model."""

    def complete(self, task: str, variables: dict[str, Any]) -> str:
        events = variables.get("events") or []
        topic_name = variables.get("topic_name") or _topic_name(events)
        if task == "aggregate":
            payload: Any = {"topics": _mock_topics(events)}
        elif task == "understand":
            payload = _mock_understanding(topic_name, events)
        elif task == "opportunity":
            payload = {
                "dimensions": {
                    "solution_space": 4,
                    "potential_gain": 4,
                    "cognitive_gain": 4,
                    "applicability": 4,
                    "necessity": 3,
                },
                "total": 3.8,
                "decision": "explore",
                "rationale": "Mock 评分：当前主题存在多个可替代路径，且与用户场景相关。",
            }
        elif task == "explore":
            payload = _mock_exploration(topic_name)
        elif task == "discovery":
            payload = {
                "title": f"当「{topic_name}」开始变复杂，可以先换一种拆法",
                "observed": f"最近共记录到 {len(events)} 条相关问题，可能围绕同一主题。",
                "comparison": "当前做法更偏向在现有结构内优化；另一条路径是先重新划分职责边界。",
            }
        elif task == "feedback":
            payload = {
                "signal": "none",
                "confidence": 0.0,
                "reason": "Mock 不执行归因；真实模式由模型判断。",
            }
        else:
            raise LLMError(f"unknown task: {task}")
        return json.dumps(payload, ensure_ascii=False)


class TraeCliLLM(BaseLLM):
    """Call ``traecli exec`` non-interactively and read the last message."""

    def __init__(self, binary: str = "traecli", timeout: int = 180):
        self.binary = binary
        self.timeout = timeout

    def complete(self, task: str, variables: dict[str, Any]) -> str:
        prompt = build_prompt(task, variables)
        with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as handle:
            output_path = Path(handle.name)
        try:
            command = [
                self.binary,
                "exec",
                "--skip-git-repo-check",
                "--output-last-message",
                str(output_path),
                prompt,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            if result.returncode != 0:
                raise LLMError(result.stderr.strip() or f"traecli exited {result.returncode}")
            return output_path.read_text(encoding="utf-8")
        finally:
            output_path.unlink(missing_ok=True)


class OpenAICompatLLM(BaseLLM):
    def __init__(self, base_url: str, model: str, api_key: str, temperature: float = 0.3, timeout: int = 180):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout

    def complete(self, task: str, variables: dict[str, Any]) -> str:
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": "You output strict JSON only."},
                {"role": "user", "content": build_prompt(task, variables)},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def build_llm(config: dict[str, Any]) -> BaseLLM:
    mode = config["llm"].get("mode", "mock")
    if mode == "mock":
        return MockLLM()
    if mode == "traecli":
        return TraeCliLLM(
            binary=config["llm"].get("traecli", "traecli"),
            timeout=int(config["llm"].get("timeout", 180)),
        )
    if mode == "openai":
        import os

        key = os.environ.get(config["llm"]["api_key_env"], "")
        if not key:
            raise LLMError(f"missing API key env: {config['llm']['api_key_env']}")
        return OpenAICompatLLM(
            base_url=config["llm"]["base_url"],
            model=config["llm"]["model"],
            api_key=key,
            temperature=float(config["llm"].get("temperature", 0.3)),
            timeout=int(config["llm"].get("timeout", 180)),
        )
    raise LLMError(f"unknown llm mode: {mode}")


# --------------------------------------------------------------------------
# Mock helpers


def _topic_name(events: list[dict[str, Any]]) -> str:
    if not events:
        return "待探索主题"
    first = str(events[0].get("user_message") or "").strip()
    return first[:18] + ("…" if len(first) > 18 else "")


def _mock_topics(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not events:
        return []
    name = _topic_name(events)
    return [
        {
            "name": name,
            "summary": f"{len(events)} 条问题可能围绕同一探索主题。",
            "event_ids": [event["event_id"] for event in events],
        }
    ]


def _mock_understanding(topic_name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "activity": f"围绕「{topic_name}」推进一项具体任务",
        "goal": "把当前问题推进到稳定、可维护的方案",
        "current_approach": "沿用现有工具与流程，在局部做优化",
        "frictions": ["上下文分散", "方案是否适用尚未验证"],
        "root_problem_hypotheses": [
            {
                "hypothesis": f"当前阻碍可能是「{topic_name}」缺少清晰的职责与边界",
                "confidence": 0.5,
                "evidence_event_ids": [event["event_id"] for event in events[:2]],
            }
        ],
        "open_questions": ["当前方案最痛的约束是什么？", "是否必须沿用现有技术栈？"],
        "notes": "Mock 输出，仅用于跑通结构。",
    }


def _mock_exploration(topic_name: str) -> dict[str, Any]:
    return {
        "directions": [
            f"在「{topic_name}」内部做局部优化",
            "换一种职责划分方式",
            "把一次性流程演进为可恢复、可观测的流程",
        ],
        "solutions": [
            {
                "name": "职责分层",
                "core_idea": "把变化快的部分与稳定的部分解耦，让每层只负责一件事。",
                "workflow": "识别职责 → 拆分边界 → 定义接口 → 分别演进",
                "components": ["现有服务", "清晰接口", "基础监控"],
                "advantages": ["边界清晰", "便于独立演进"],
                "constraints": ["前期需要接口设计", "跨层排障成本上升"],
                "requirements": ["明确各层职责"],
                "applicability": "系统开始变复杂、职责混杂时",
                "relationship": "alternative",
                "evidence": ["Mock 示例：接入真实搜索后补充可访问资料"],
            },
            {
                "name": "补齐可观测性与失败恢复",
                "core_idea": "不改变整体架构，先补上当前最痛的短板。",
                "workflow": "定位失败点 → 增加日志/重试 → 验证恢复",
                "components": ["日志", "重试", "告警"],
                "advantages": ["改动小", "见效快"],
                "constraints": ["不解决结构性问题"],
                "requirements": ["能定位关键失败点"],
                "applicability": "当前方案基本可用但稳定性不足时",
                "relationship": "complementary",
                "evidence": ["Mock 示例"],
            },
            {
                "name": "演进为可恢复的工作流",
                "core_idea": "把任务从一次性执行变成有状态、可恢复的流程。",
                "workflow": "定义状态 → 持久化 → 失败恢复 → 观测",
                "components": ["状态存储", "工作流引擎或任务队列"],
                "advantages": ["可恢复", "可观测"],
                "constraints": ["引入新的运行时组件"],
                "requirements": ["任务需要长期运行或人工介入"],
                "applicability": "任务规模与复杂度持续上升时",
                "relationship": "evolutionary",
                "evidence": ["Mock 示例"],
            },
        ],
        "search_queries": [f"{topic_name} 架构 替代方案", f"{topic_name} 最佳实践"],
    }
