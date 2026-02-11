from __future__ import annotations

from claw_demo.llm.schemas import LLMResponseEnvelope, SkillCall


def plan_locally(user_text: str) -> LLMResponseEnvelope:
    text = user_text.strip()
    low = text.lower()

    if "天气" in text or "weather" in low:
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="weather", args={"request": text}), text="")

    if "查文件" in text or "file_search" in low:
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="file_search", args={"request": text}), text="")

    if "读文件" in text or "file_read" in low:
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="file_read", args={"request": text}), text="")

    if "摘要" in text or "summarize" in low:
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="summarize", args={"request": text}), text="")

    if "发邮件" in text or "email" in low:
        return LLMResponseEnvelope(
            type="skill_call",
            skill=SkillCall(
                name="email",
                args={"request": text},
            ),
            text="",
        )

    return LLMResponseEnvelope(type="final", text="我已收到。你可以让我查天气、查文件、读文件、摘要或发邮件。")
