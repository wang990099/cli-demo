from __future__ import annotations

import re

from claw_demo.llm.schemas import LLMResponseEnvelope, SkillCall


def plan_locally(user_text: str) -> LLMResponseEnvelope:
    text = user_text.strip()
    low = text.lower()

    if "天气" in text or "weather" in low:
        city = "Shanghai"
        if "北京" in text:
            city = "Beijing"
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="weather", args={"city": city}), text="")

    if "查文件" in text or "file_search" in low:
        query = ""
        match = re.search(r"[""']([^""']+)[""']", text)
        if match:
            query = match.group(1)
        if not query:
            query = text.split()[-1] if text.split() else ""
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="file_search", args={"query": query or "py", "path": "./"}), text="")

    if "读文件" in text or "file_read" in low:
        path = "README.md"
        match = re.search(r"([\w./-]+\.[\w]+)", text)
        if match:
            path = match.group(1)
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="file_read", args={"path": path}), text="")

    if "摘要" in text or "summarize" in low:
        payload = text.split("摘要", 1)[-1].strip() or text
        return LLMResponseEnvelope(type="skill_call", skill=SkillCall(name="summarize", args={"text": payload}), text="")

    if "发邮件" in text or "email" in low:
        return LLMResponseEnvelope(
            type="skill_call",
            skill=SkillCall(
                name="email",
                args={
                    "to": "demo@example.com",
                    "subject": "CLI Demo",
                    "body": text,
                },
            ),
            text="",
        )

    return LLMResponseEnvelope(type="final", text="我已收到。你可以让我查天气、查文件、读文件、摘要或发邮件。")
