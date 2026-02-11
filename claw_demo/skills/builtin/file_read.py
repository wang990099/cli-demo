from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from claw_demo.skills.models import SkillContext, SkillResult


class FileReadArgs(BaseModel):
    path: str


def _is_under_allowed(path: Path, allowed_roots: list[str], project_root: Path) -> bool:
    resolved = path.resolve()
    for root in allowed_roots:
        root_path = (project_root / root).resolve()
        if resolved == root_path or root_path in resolved.parents:
            return True
    return False


def run(args: FileReadArgs, ctx: SkillContext) -> SkillResult:
    target = (ctx.workspace_root / args.path).resolve()
    if not _is_under_allowed(target, ctx.config.file_access.allowed_roots, ctx.workspace_root):
        return SkillResult(ok=False, text="路径不在允许范围内")
    if not target.exists() or not target.is_file():
        return SkillResult(ok=False, text="文件不存在")

    size = target.stat().st_size
    if size > ctx.config.file_access.max_read_bytes:
        return SkillResult(ok=False, text="文件超过读取大小限制")

    content = target.read_text(encoding="utf-8", errors="replace")
    return SkillResult(ok=True, text=content)
