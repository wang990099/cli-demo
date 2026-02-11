from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_demo.config.schema import Config
from claw_demo.config.workspace import resolve_workspace_dir
from claw_demo.skills.models import SkillContext, SkillResult
from claw_demo.skills.toolbox import TOOL_SCHEMAS, ToolExecutor


@dataclass
class WorkflowRunResult:
    ok: bool
    text: str
    tool_trace: list[str]


class WorkflowAgentRunner:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.workspace_root = resolve_workspace_dir(config, project_root)
        self.tool_executor = ToolExecutor()
        self._client = None
        if config.llm.api_key:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=config.llm.base_url,
                api_key=config.llm.api_key,
                timeout=config.llm.timeout_sec,
            )

    def run(
        self,
        user_input: str,
        recent_messages: list[dict[str, str]] | None = None,
        memory_snippets: list[str] | None = None,
    ) -> WorkflowRunResult:
        if self._client is None:
            return WorkflowRunResult(
                ok=False,
                text="LLM 不可用，无法执行工作流任务。请配置 llm.api_key。",
                tool_trace=[],
            )

        recent_messages = recent_messages or []
        memory_snippets = memory_snippets or []
        required_tools = self._required_tools(user_input)
        called_tools_set: set[str] = set()
        trace_lines: list[str] = []

        ctx = SkillContext(config=self.config, project_root=self.project_root, workspace_root=self.workspace_root)
        system = self._build_system_prompt(memory_snippets, recent_messages)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_input},
        ]

        max_steps = max(2, int(self.config.skills.max_steps))
        for _ in range(max_steps):
            resp = self._client.chat.completions.create(
                model=self.config.llm.model,
                messages=messages,
                temperature=self.config.llm.temperature,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            msg = resp.choices[0].message
            tool_calls = msg.tool_calls or []

            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tool_args = {}
                    res = self.tool_executor.execute(tool_name, tool_args, ctx)
                    called_tools_set.add(tool_name)
                    trace_lines.append(self._trace_line(tool_name, tool_args, res))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": res.text,
                        }
                    )
                continue

            answer = (msg.content or "").strip()
            if answer:
                missing = [name for name in required_tools if name not in called_tools_set]
                if missing:
                    trace_lines.append(f"missing-required-tools: {', '.join(missing)}")
                    messages.append(
                        {
                            "role": "assistant",
                            "content": answer,
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "你尚未完成全部用户目标。缺少步骤: "
                                + ", ".join(missing)
                                + "。请继续调用必要工具，最后再给最终答复。"
                            ),
                        }
                    )
                    continue
                return WorkflowRunResult(ok=True, text=answer, tool_trace=trace_lines)

            messages.append({"role": "user", "content": "请继续执行并给出最终答复。"})

        return WorkflowRunResult(
            ok=False,
            text="工作流执行超出最大步骤，请重试或拆分任务。",
            tool_trace=trace_lines,
        )

    def _trace_line(self, tool_name: str, tool_args: dict[str, Any], result: SkillResult) -> str:
        args_preview = json.dumps(tool_args, ensure_ascii=False)
        text_preview = (result.text or "").replace("\n", " ")
        if len(text_preview) > 120:
            text_preview = text_preview[:120] + "..."
        status = "ok" if result.ok else "error"
        return f"{tool_name} args={args_preview} -> {status}: {text_preview}"

    def _required_tools(self, user_input: str) -> list[str]:
        text = user_input.lower()
        required_set: set[str] = set()

        if any(k in user_input for k in ["搜索", "查找", "找文件"]) or "file_search" in text:
            required_set.add("file_search")
        if any(k in user_input for k in ["读取", "读文件", "查看文件"]) or "file_read" in text:
            required_set.add("file_read")
        if "总结" in user_input or "摘要" in user_input or "summarize" in text:
            required_set.add("summarize")
        if "发送" in user_input or "发邮件" in user_input or "email" in text:
            required_set.add("email")
        if "天气" in user_input or "weather" in text:
            required_set.add("weather")
        if any(k in user_input for k in ["时间", "几点", "现在几"]) or "time" in text:
            required_set.add("time")

        # Compound pattern: "搜索...文件，将文件总结，发送给xx@xx"
        if re.search(r"发送给\s*\S+@", user_input):
            for item in ["file_search", "file_read", "summarize", "email"]:
                required_set.add(item)

        canonical_order = ["file_search", "file_read", "summarize", "email", "weather", "time"]
        return [name for name in canonical_order if name in required_set]

    def _build_system_prompt(self, memory_snippets: list[str], recent_messages: list[dict[str, str]]) -> str:
        memory_text = "\n".join(memory_snippets[:5]) if memory_snippets else "(empty)"
        recent_text = "\n".join(
            f"{m.get('role','')}: {m.get('content','')}" for m in recent_messages[-6:]
        )
        return (
            "你是 Workflow Agent，负责完整完成用户目标。"
            "\n必须遵循:"
            "\n1) 先理解完整任务，不要只完成第一步。"
            "\n2) 需要时连续调用多个工具直到目标完成。"
            "\n3) 工具结果为事实依据，不得编造。"
            "\n4) 输出最终答案前，确保所有子目标已完成。"
            f"\n工作目录: {self.workspace_root}"
            f"\n长期记忆:\n{memory_text}"
            f"\n最近对话:\n{recent_text if recent_text else '(empty)'}"
        )
