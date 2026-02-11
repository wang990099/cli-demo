from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from claw_demo.config.schema import Config
from claw_demo.memory.grep_retriever import MemoryEntry


class MemoryRecord(BaseModel):
    key: str = Field(min_length=1)
    mem_type: str = Field(pattern="^(profile|fact|episode)$")
    tags: list[str] = Field(default_factory=list)
    content: str = Field(min_length=1)


class MemoryRecordList(BaseModel):
    records: list[MemoryRecord] = Field(default_factory=list)


class MemoryVerifyDecision(BaseModel):
    keep: list[int] = Field(default_factory=list)


class MemoryExtractor(Protocol):
    def extract(self, user_text: str, recent_messages: list[dict[str, str]] | None = None) -> list[MemoryEntry]:
        ...


class MemoryVerifier(Protocol):
    def verify(
        self,
        user_text: str,
        entries: list[MemoryEntry],
        recent_messages: list[dict[str, str]] | None = None,
    ) -> list[MemoryEntry]:
        ...


def _build_client(config: Config):
    if not config.llm.api_key:
        return None
    from openai import OpenAI

    return OpenAI(
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        timeout=config.llm.timeout_sec,
    )


@dataclass
class LLMMemoryExtractor:
    config: Config

    def __post_init__(self) -> None:
        self._client = _build_client(self.config)

    def extract(self, user_text: str, recent_messages: list[dict[str, str]] | None = None) -> list[MemoryEntry]:
        text = user_text.strip()
        if not text or self._client is None:
            return []

        context_text = self._format_recent_context(recent_messages)
        prompt = (
            "你是记忆抽取器。基于用户最新输入和少量上下文，提取值得长期保留的信息。"
            "允许自由理解后存储，但必须输出 JSON 对象，格式为: "
            '{"records":[{"key":"...","mem_type":"profile|fact|episode","tags":["..."],"content":"..."}]}。'
            "规则: 1) 无长期价值返回 {\"records\":[]}。"
            "2) key 要语义稳定，可随意设计但应可复用。"
            "3) content 用中文简洁陈述，不带解释。"
            "4) 含明显阶段性进展/会议/计划/总结等信息时，优先使用 episode。"
            f"\n上下文:\n{context_text}"
            f"\n用户输入:\n{text}"
        )

        retries = self.config.llm.max_retries
        for attempt in range(retries + 1):
            resp = self._client.chat.completions.create(
                model=self.config.llm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = (resp.choices[0].message.content or "").strip()
            parsed = self._parse_records(raw)
            if parsed is not None:
                today = date.today().isoformat()
                return [
                    MemoryEntry(
                        key=record.key,
                        mem_type=record.mem_type,
                        tags=record.tags,
                        updated_at=today,
                        content=record.content,
                        source_file=None,
                    )
                    for record in parsed.records
                ]
            if attempt < retries:
                prompt = prompt + "\n请只返回合法 JSON，不要输出其他文本。"
        return []

    def _format_recent_context(self, recent_messages: list[dict[str, str]] | None) -> str:
        recent_messages = recent_messages or []
        lines: list[str] = []
        for msg in recent_messages[-6:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines) if lines else "(empty)"

    def _parse_records(self, raw: str) -> MemoryRecordList | None:
        if not raw:
            return None
        candidate = raw
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            candidate = match.group(0)
        try:
            payload = json.loads(candidate)
            return MemoryRecordList.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            return None


@dataclass
class LLMMemoryVerifier:
    config: Config

    def __post_init__(self) -> None:
        self._client = _build_client(self.config)

    def verify(
        self,
        user_text: str,
        entries: list[MemoryEntry],
        recent_messages: list[dict[str, str]] | None = None,
    ) -> list[MemoryEntry]:
        if not entries:
            return []
        fallback = self._fallback_verify(entries)
        if self._client is None:
            return fallback

        candidate_json = json.dumps(
            [
                {
                    "idx": i,
                    "key": e.key,
                    "mem_type": e.mem_type,
                    "tags": e.tags,
                    "content": e.content,
                }
                for i, e in enumerate(entries)
            ],
            ensure_ascii=False,
        )
        prompt = (
            "你是记忆审核器。请从候选记忆中保留真正值得长期保存的条目。"
            "只返回 JSON：{\"keep\":[index,...]}。"
            "规则: 删除冗余、过短、无事实价值、纯礼貌语。"
            f"\n用户输入: {user_text}"
            f"\n候选记忆: {candidate_json}"
        )

        retries = self.config.llm.max_retries
        for attempt in range(retries + 1):
            resp = self._client.chat.completions.create(
                model=self.config.llm.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = (resp.choices[0].message.content or "").strip()
            decision = self._parse_decision(raw)
            if decision is not None:
                keep_set = set(i for i in decision.keep if 0 <= i < len(entries))
                return [entry for i, entry in enumerate(entries) if i in keep_set]
            if attempt < retries:
                prompt = prompt + "\n请只返回合法 JSON，不要输出其他文本。"

        return fallback

    def _parse_decision(self, raw: str) -> MemoryVerifyDecision | None:
        if not raw:
            return None
        candidate = raw
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            candidate = match.group(0)
        try:
            payload = json.loads(candidate)
            return MemoryVerifyDecision.model_validate(payload)
        except (json.JSONDecodeError, ValidationError):
            return None

    def _fallback_verify(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        filtered: list[MemoryEntry] = []
        seen: set[tuple[str, str]] = set()
        for entry in entries:
            content = entry.content.strip()
            if len(content) < 4:
                continue
            if content.endswith("?") or content.endswith("？"):
                continue
            k = (entry.key, content)
            if k in seen:
                continue
            seen.add(k)
            filtered.append(entry)
            if len(filtered) >= 5:
                break
        return filtered
