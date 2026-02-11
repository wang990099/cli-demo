from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from claw_demo.config.schema import Config
from claw_demo.config.workspace import resolve_workspace_dir
from claw_demo.skills.models import SkillContext, SkillResult
from claw_demo.skills.registry import build_skill_specs


class SkillDispatcher:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.workspace_root = resolve_workspace_dir(config, project_root)
        self.specs = build_skill_specs()

    def enabled_skills(self) -> list[str]:
        return [name for name in self.config.skills.enabled if name in self.specs]

    def health_check(self) -> dict[str, str]:
        report: dict[str, str] = {}
        for name in self.enabled_skills():
            if name == "email":
                script = self.project_root / "claw_demo" / "skills" / "external" / "email_skill" / "run.py"
                report[name] = "ok" if script.exists() else "missing run.py"
            else:
                report[name] = "ok"
        return report

    def dispatch(self, name: str, args: dict[str, Any]) -> SkillResult:
        if name not in self.enabled_skills():
            return SkillResult(ok=False, text=f"skill 未启用或不存在: {name}")

        if name == "email":
            return self._dispatch_email(args)

        spec = self.specs[name]
        try:
            parsed_args = spec.args_model.model_validate(args)
        except ValidationError as exc:
            return SkillResult(ok=False, text=f"skill 参数校验失败: {exc}")

        ctx = SkillContext(
            config=self.config,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
        )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(spec.runner, parsed_args, ctx)
            try:
                return future.result(timeout=self.config.skills.timeout_sec)
            except FuturesTimeoutError:
                return SkillResult(ok=False, text=f"skill 执行超时: {name}")
            except Exception as exc:  # pragma: no cover
                return SkillResult(ok=False, text=f"skill 执行失败: {exc}")

    def _dispatch_email(self, args: dict[str, Any]) -> SkillResult:
        spec = self.specs["email"]
        try:
            parsed_args = spec.args_model.model_validate(args)
        except ValidationError as exc:
            return SkillResult(ok=False, text=f"skill 参数校验失败: {exc}")

        script = self.project_root / "claw_demo" / "skills" / "external" / "email_skill" / "run.py"
        if not script.exists():
            return SkillResult(ok=False, text="email skill 脚本不存在")

        payload = {
            "args": parsed_args.model_dump(),
            "config": self.config.email.model_dump(by_alias=True),
        }

        try:
            proc = subprocess.run(
                [sys.executable, str(script)],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                timeout=self.config.skills.timeout_sec,
                check=False,
            )
            out = proc.stdout.strip() or "{}"
            parsed = json.loads(out)
            return SkillResult(ok=bool(parsed.get("ok")), text=str(parsed.get("text", "")), data=parsed)
        except subprocess.TimeoutExpired:
            return SkillResult(ok=False, text="email skill 执行超时")
        except Exception as exc:  # pragma: no cover
            return SkillResult(ok=False, text=f"email skill 执行失败: {exc}")
