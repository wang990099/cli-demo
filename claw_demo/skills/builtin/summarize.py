from __future__ import annotations

from pydantic import BaseModel, Field

from claw_demo.skills.models import SkillContext, SkillResult


class SummarizeArgs(BaseModel):
    text: str = Field(min_length=1)


def _chunks(text: str, chunk_size: int = 1000) -> list[str]:
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _summarize_chunk(chunk: str) -> str:
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    if not lines:
        return ""
    if len(lines) <= 3:
        return " ".join(lines)
    return " ".join(lines[:2] + ["...", lines[-1]])


def run(args: SummarizeArgs, ctx: SkillContext) -> SkillResult:
    chunks = _chunks(args.text, chunk_size=ctx.config.chat.max_context_chars // 3)
    partials = [_summarize_chunk(c) for c in chunks]
    final = "\n".join(f"- {p}" for p in partials if p)
    return SkillResult(ok=True, text=final or "无可摘要内容")
