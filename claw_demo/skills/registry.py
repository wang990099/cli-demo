from __future__ import annotations

from pydantic import BaseModel

from claw_demo.skills.builtin import file_read, file_search, summarize, weather
from claw_demo.skills.models import SkillResult, SkillSpec


class EmailArgs(BaseModel):
    to: str
    subject: str
    body: str


def _placeholder_email(_: BaseModel, __) -> SkillResult:
    return SkillResult(ok=False, text="email skill should be executed as external skill")


def build_skill_specs() -> dict[str, SkillSpec]:
    return {
        "weather": SkillSpec("weather", "查询天气", weather.WeatherArgs, weather.run),
        "file_search": SkillSpec("file_search", "按文件名搜索", file_search.FileSearchArgs, file_search.run),
        "file_read": SkillSpec("file_read", "读取文件", file_read.FileReadArgs, file_read.run),
        "summarize": SkillSpec("summarize", "文本摘要", summarize.SummarizeArgs, summarize.run),
        "email": SkillSpec("email", "发送邮件", EmailArgs, _placeholder_email),
    }
