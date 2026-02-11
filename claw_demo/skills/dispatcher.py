from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_demo.config.schema import Config
from claw_demo.config.workspace import resolve_workspace_dir
from claw_demo.skills.loader import SkillLoader
from claw_demo.skills.models import AgentSkillSpec, SkillContext, SkillResult
from claw_demo.skills.toolbox import TOOL_SCHEMAS, ToolExecutor


@dataclass
class SkillCheckReport:
    status: str
    issues: list[str]
    warnings: list[str]
    runtime: list[str]


class AgentSkillDispatcher:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.workspace_root = resolve_workspace_dir(config, project_root)
        skills_root = Path(__file__).resolve().parent
        import_roots = [Path(p).expanduser().resolve() for p in config.skills.import_dirs if str(p).strip()]
        self.loader = SkillLoader(skills_root, import_roots=import_roots)
        self.tool_executor = ToolExecutor()
        self._client = None
        if config.llm.api_key:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=config.llm.base_url,
                api_key=config.llm.api_key,
                timeout=config.llm.timeout_sec,
            )

    def enabled_skills(self) -> list[str]:
        enabled = set(self.config.skills.enabled)
        return [spec.name for spec in self.loader.list_skills() if spec.name in enabled]

    def health_check(self) -> dict[str, str]:
        detailed = self.health_check_detailed()
        return {name: detail.status for name, detail in detailed.items()}

    def health_check_detailed(self) -> dict[str, SkillCheckReport]:
        reports: dict[str, SkillCheckReport] = {}
        enabled = list(dict.fromkeys(self.config.skills.enabled))
        tool_names = {t["function"]["name"] for t in TOOL_SCHEMAS}

        for requested_name in enabled:
            issues: list[str] = []
            warnings: list[str] = []
            runtime: list[str] = []

            spec = self.loader.load(requested_name)
            if spec is None:
                reports[requested_name] = SkillCheckReport(
                    status="error",
                    issues=["missing SKILL.md"],
                    warnings=[],
                    runtime=[],
                )
                continue

            if spec.name != requested_name:
                warnings.append(f"skill name mismatch: dir={requested_name}, manifest={spec.name}")
            if spec.source_path.as_posix().find("/skills/agents/") == -1:
                runtime.append(f"external source: {spec.source_path}")
            if not spec.description.strip():
                warnings.append("description is empty")
            if len(spec.instructions.strip()) < 20:
                warnings.append("instructions too short (<20 chars)")
            if spec.name not in tool_names:
                issues.append(f"no tool binding for skill name: {spec.name}")
            if self._client is None:
                issues.append("llm unavailable for agent-skill execution")
            else:
                runtime.append("llm available")

            status = "ok"
            if issues:
                status = "error"
            elif warnings:
                status = "warn"

            reports[requested_name] = SkillCheckReport(
                status=status,
                issues=issues,
                warnings=warnings,
                runtime=runtime,
            )

        return reports

    def dispatch(
        self,
        name: str,
        request_text: str,
        recent_messages: list[dict[str, str]] | None = None,
        memory_snippets: list[str] | None = None,
    ) -> SkillResult:
        if name not in self.enabled_skills():
            return SkillResult(ok=False, text=f"skill 未启用或不存在: {name}")

        spec = self.loader.load(name)
        if spec is None:
            return SkillResult(ok=False, text=f"skill 配置缺失: {name}")

        if self._client is None:
            return SkillResult(ok=False, text="LLM 不可用，Agent Skills 无法执行。请配置 llm.api_key。")

        ctx = SkillContext(config=self.config, project_root=self.project_root, workspace_root=self.workspace_root)
        return self._agent_execute(spec, request_text, ctx, recent_messages or [], memory_snippets or [])

    def _agent_execute(
        self,
        spec: AgentSkillSpec,
        request_text: str,
        ctx: SkillContext,
        recent_messages: list[dict[str, str]],
        memory_snippets: list[str],
    ) -> SkillResult:
        recent_text = "\n".join(f"{m.get('role','')}: {m.get('content','')}" for m in recent_messages[-6:])
        memory_text = "\n".join(memory_snippets[:5]) if memory_snippets else "(empty)"
        system = (
            "你是技能代理执行器。"
            f"\n技能名: {spec.name}"
            f"\n技能描述: {spec.description}"
            f"\n技能说明:\n{spec.instructions}"
            "\n执行原则: 你可以自由决定步骤；必要时调用工具；最终必须给出可直接返回给用户的答案。"
            f"\n工作目录: {ctx.workspace_root}"
            f"\n长期记忆:\n{memory_text}"
            f"\n最近对话:\n{recent_text if recent_text else '(empty)'}"
        )

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": request_text},
        ]

        max_steps = max(1, int(self.config.skills.max_steps))
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
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_result = self.tool_executor.execute(tc.function.name, args, ctx)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_result.text,
                        }
                    )
                continue

            text = (msg.content or "").strip()
            if text:
                return SkillResult(ok=True, text=text)

            messages.append({"role": "assistant", "content": "请给出最终答案。"})

        return SkillResult(ok=False, text="技能代理执行超出最大步骤，请重试。")
