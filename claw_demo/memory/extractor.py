from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from claw_demo.memory.grep_retriever import MemoryEntry


_TRAILING_PARTICLE_RE = re.compile(r"[了呀啊吧呢嘛]$")
_QUESTION_HINTS = ("?", "？", "什么", "吗", "么")
_SPLIT_RE = re.compile(r"(?:、|,|，|以及|及|和|与|还有)")


def _clean_item(text: str) -> str:
    value = text.strip()
    value = _TRAILING_PARTICLE_RE.sub("", value)
    return value.strip()


def _split_items(fragment: str) -> list[str]:
    parts = [_clean_item(p) for p in _SPLIT_RE.split(fragment)]
    return [p for p in parts if p]


def parse_pref_items(content: str) -> list[str]:
    raw = content.strip()
    if ":" in raw:
        raw = raw.split(":", 1)[1].strip()
    items = _split_items(raw)
    deduped: list[str] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def format_pref_content(kind: str, items: list[str]) -> str:
    label = "喜欢" if kind == "like" else "不喜欢"
    return f"{label}: {'、'.join(items)}"


@dataclass
class MemoryExtractionResult:
    likes: list[str]
    dislikes: list[str]
    additional_entries: list[MemoryEntry]


def extract_memory(user_text: str) -> MemoryExtractionResult:
    text = user_text.strip()
    if not text:
        return MemoryExtractionResult(likes=[], dislikes=[], additional_entries=[])
    if any(hint in text for hint in _QUESTION_HINTS):
        return MemoryExtractionResult(likes=[], dislikes=[], additional_entries=[])

    entries: list[MemoryEntry] = []
    today = date.today().isoformat()

    like_fragments = re.findall(r"(?:我)?(?:还)?喜欢(.+?)(?:(?:，|,)?不喜欢|[。！？!?]|$)", text)
    dislike_fragments = re.findall(r"(?:我)?(?:还)?不喜欢(.+?)(?:[。！？!?]|$)", text)

    likes: list[str] = []
    for fragment in like_fragments:
        likes.extend(_split_items(fragment))
    dislikes: list[str] = []
    for fragment in dislike_fragments:
        dislikes.extend(_split_items(fragment))

    likes = [v for i, v in enumerate(likes) if v and v not in likes[:i]]
    dislikes = [v for i, v in enumerate(dislikes) if v and v not in dislikes[:i]]
    likes = [v for v in likes if v not in dislikes]

    if "我正在做" in text:
        entries.append(
            MemoryEntry(
                key="project:current",
                mem_type="fact",
                tags=["project", "auto"],
                updated_at=today,
                content=text,
                source_file=None,
            )
        )
    if "我的目标是" in text:
        entries.append(
            MemoryEntry(
                key="goal:current",
                mem_type="fact",
                tags=["goal", "auto"],
                updated_at=today,
                content=text,
                source_file=None,
            )
        )
    return MemoryExtractionResult(likes=likes, dislikes=dislikes, additional_entries=entries)


def extract_memory_entry(user_text: str) -> MemoryEntry | None:
    result = extract_memory(user_text)
    return result.additional_entries[0] if result.additional_entries else None
