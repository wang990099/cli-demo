from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SkillCall(BaseModel):
    name: str
    args: dict


class LLMResponseEnvelope(BaseModel):
    type: Literal["final", "skill_call"]
    text: str = ""
    skill: SkillCall | None = None
