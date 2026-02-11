from __future__ import annotations

from datetime import date

from claw_demo.memory.grep_retriever import MemoryEntry


_RULES = [
    ("我喜欢", "pref"),
    ("我不喜欢", "pref"),
    ("我正在做", "project"),
    ("我的目标是", "goal"),
]


def extract_memory_entry(user_text: str) -> MemoryEntry | None:
    text = user_text.strip()
    if not text:
        return None
    for phrase, prefix in _RULES:
        if phrase in text:
            key = f"{prefix}:{abs(hash(text)) % 100000}"
            mem_type = "profile" if prefix == "pref" else "fact"
            tags = [prefix, "auto"]
            return MemoryEntry(
                key=key,
                mem_type=mem_type,
                tags=tags,
                updated_at=date.today().isoformat(),
                content=text,
                source_file=None,  # type: ignore[arg-type]
            )
    return None
