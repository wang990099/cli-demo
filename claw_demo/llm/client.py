from __future__ import annotations

import json
from collections.abc import Iterator

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
            '{"type":"final|skill_call","text":"...","skill":{"name":"...","args":{"request":"..."}}}。'
            f"可用技能: {', '.join(skill_names)}。"
            f"长期记忆: {' | '.join(memory_snippets[:3])}"
        )
        req_messages = [{"role": "system", "content": system_prompt}] + messages

        content = self._call_json(req_messages)
        if content is None:
            return LLMResponseEnvelope(type="final", text=user_text)
        return content

    def finalize_with_skill(self, user_text: str, skill_name: str, skill_result_text: str) -> str:
        return "".join(self.finalize_with_skill_stream(user_text, skill_name, skill_result_text))

    def finalize_with_skill_stream(
        self,
        user_text: str,
        skill_name: str,
        skill_result_text: str,
    ) -> Iterator[str]:
        if self._client is None:
            yield from self.stream_text(f"已执行 {skill_name}:\n{skill_result_text}")
            return

        for chunk in self._stream_completion(
            user_text=user_text,
            skill_name=skill_name,
            skill_result_text=skill_result_text,
        ):
            yield chunk

    def stream_text(self, text: str, chunk_size: int = 16) -> Iterator[str]:
        normalized = text or ""
        for i in range(0, len(normalized), chunk_size):
            yield normalized[i : i + chunk_size]

    def _stream_completion(
        self,
        user_text: str,
        skill_name: str,
        skill_result_text: str,
    ) -> Iterator[str]:
        prompt = (
            "请基于以下信息用简洁中文回答用户。"
            f"\n用户: {user_text}\n技能: {skill_name}\n结果: {skill_result_text}"
        )
        stream = self._client.chat.completions.create(
            model=self.config.llm.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.config.llm.temperature,
            stream=True,
        )
        emitted = False
        for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            content = (delta.content or "") if delta else ""
            if content:
                emitted = True
                yield content
        if not emitted:
            # Stream mode can occasionally yield empty deltas only.
            yield skill_result_text

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
