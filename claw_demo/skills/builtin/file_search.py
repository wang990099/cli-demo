from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from claw_demo.skills.models import SkillContext, SkillResult


class FileSearchArgs(BaseModel):
    query: str = Field(min_length=1)
    path: str = "./"


def _is_under_allowed(path: Path, allowed_roots: list[str], project_root: Path) -> bool:
    resolved = path.resolve()
    for root in allowed_roots:
        root_path = (project_root / root).resolve()
        if resolved == root_path or root_path in resolved.parents:
            return True
    return False


def run(args: FileSearchArgs, ctx: SkillContext) -> SkillResult:
    root = (ctx.workspace_root / args.path).resolve()
    if not _is_under_allowed(root, ctx.config.file_access.allowed_roots, ctx.workspace_root):
        return SkillResult(ok=False, text="路径不在允许范围内")

    matches: list[str] = []
    query_l = args.query.lower()
    for p in root.rglob("*"):
        if query_l in p.name.lower():
            matches.append(str(p.relative_to(ctx.workspace_root)))
        if len(matches) >= 20:
            break

    if not matches:
        return SkillResult(ok=True, text="未找到匹配文件", data={"matches": []})
    return SkillResult(ok=True, text="\n".join(matches), data={"matches": matches})
