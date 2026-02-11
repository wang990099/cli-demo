from __future__ import annotations

import json
from typing import Any

from claw_demo.config.schema import Config
from claw_demo.llm.planner import plan_locally
from claw_demo.llm.schemas import LLMResponseEnvelope


class LLMClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = None
        if config.llm.api_key:
            from openai import OpenAI

            self._client = OpenAI(base_url=config.llm.base_url, api_key=config.llm.api_key, timeout=config.llm.timeout_sec)

    def plan_or_answer(self, messages: list[dict[str, str]], memory_snippets: list[str], skill_names: list[str]) -> LLMResponseEnvelope:
        user_text = messages[-1]["content"] if messages else ""
        if self._client is None:
            return plan_locally(user_text)

        system_prompt = (
            "你是 CLI AI 助手。"
            "必须返回 JSON，格式为:"
            '{"type":"final|skill_call","text":"...","skill":{"name":"...","args":{}}}。'
            f"可用技能: {', '.join(skill_names)}。"
            f"长期记忆: {' | '.join(memory_snippets[:3])}"
        )
        req_messages = [{"role": "system", "content": system_prompt}] + messages

        content = self._call_json(req_messages)
        if content is None:
            return LLMResponseEnvelope(type="final", text=user_text)
        return content

    def finalize_with_skill(self, user_text: str, skill_name: str, skill_result_text: str) -> str:
        if self._client is None:
            return f"已执行 {skill_name}:\n{skill_result_text}"

        prompt = (
            "请基于以下信息用简洁中文回答用户。"
            f"\n用户: {user_text}\n技能: {skill_name}\n结果: {skill_result_text}"
        )
        resp = self._client.chat.completions.create(
            model=self.config.llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.llm.temperature,
        )
        return resp.choices[0].message.content or skill_result_text

    def _call_json(self, messages: list[dict[str, str]]) -> LLMResponseEnvelope | None:
        retry = self.config.llm.max_retries
        for attempt in range(retry + 1):
            resp = self._client.chat.completions.create(
                model=self.config.llm.model,
                messages=messages,
                temperature=self.config.llm.temperature,
            )
            text = resp.choices[0].message.content or ""
            parsed = self._parse_envelope(text)
            if parsed is not None:
                return parsed
            if attempt < retry:
                messages = messages + [{"role": "user", "content": "请只返回合法 JSON，不要输出其他文本。"}]
        return None

    def _parse_envelope(self, text: str) -> LLMResponseEnvelope | None:
        raw = text.strip()
        if not raw:
            return None
        try:
            return LLMResponseEnvelope.model_validate(json.loads(raw))
        except Exception:
            return None
