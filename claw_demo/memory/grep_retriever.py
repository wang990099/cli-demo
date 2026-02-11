from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from math import exp
from pathlib import Path


@dataclass
class MemoryEntry:
    key: str
    mem_type: str
    tags: list[str]
    updated_at: str
    content: str
    source_file: Path | None


@dataclass
class RetrievedMemory:
    entry: MemoryEntry
    score: float
    snippet: str


_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_UPDATED_RE = re.compile(r"^-\s*updated_at:\s*(.+)$", re.MULTILINE)
_TYPE_RE = re.compile(r"^-\s*type:\s*(.+)$", re.MULTILINE)
_TAGS_RE = re.compile(r"^-\s*tags:\s*(.+)$", re.MULTILINE)
_CONTENT_RE = re.compile(r"^-\s*content:\s*(.+)$", re.MULTILINE)


def normalize_query(text: str) -> list[str]:
    lowered = text.lower()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", lowered)
    tokens = [tok for tok in normalized.split() if tok]
    # Improve Chinese recall for queries like "我喜欢什么" by adding common intent tokens.
    if "不喜欢" in lowered:
        tokens.extend(["不喜欢", "dislike", "pref"])
    if "喜欢" in lowered:
        tokens.extend(["喜欢", "like", "pref"])
    if "目标" in lowered:
        tokens.extend(["目标", "goal"])
    if "正在做" in lowered:
        tokens.extend(["正在做", "project"])
    # Add CJK bigrams so contiguous Chinese queries can match memory snippets.
    for segment in re.findall(r"[\u4e00-\u9fff]+", lowered):
        if len(segment) < 2:
            continue
        tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
    return list(dict.fromkeys(tokens))


def _parse_entries(md_path: Path) -> list[MemoryEntry]:
    if not md_path.exists():
        return []
    text = md_path.read_text(encoding="utf-8")
    headers = list(_HEADER_RE.finditer(text))
    if not headers:
        return []

    entries: list[MemoryEntry] = []
    for idx, match in enumerate(headers):
        start = match.start()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(text)
        block = text[start:end]
        key = match.group(1).strip()
        mem_type = (_TYPE_RE.search(block).group(1).strip() if _TYPE_RE.search(block) else "fact")
        tags_raw = _TAGS_RE.search(block).group(1).strip() if _TAGS_RE.search(block) else ""
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        updated_at = _UPDATED_RE.search(block).group(1).strip() if _UPDATED_RE.search(block) else "1970-01-01"
        content = _CONTENT_RE.search(block).group(1).strip() if _CONTENT_RE.search(block) else ""
        entries.append(
            MemoryEntry(
                key=key,
                mem_type=mem_type,
                tags=tags,
                updated_at=updated_at,
                content=content,
                source_file=md_path,
            )
        )
    return entries


def load_all_entries(memory_root: Path) -> list[MemoryEntry]:
    files = [memory_root / "profile.md", memory_root / "facts.md"]
    files.extend(sorted((memory_root / "episodes").glob("*.md")))
    entries: list[MemoryEntry] = []
    for file in files:
        entries.extend(_parse_entries(file))
    return entries


def _age_days(updated_at: str) -> int | None:
    try:
        date = datetime.strptime(updated_at[:10], "%Y-%m-%d")
        age = datetime.utcnow() - date
        return max(0, age.days)
    except ValueError:
        return None


def _snippet(entry: MemoryEntry, query_tokens: list[str]) -> str:
    text = f"{entry.content}\n{entry.key}" if entry.content else entry.key
    if not query_tokens:
        return text[:240]

    lines = text.splitlines()
    for line in lines:
        if not line.strip():
            continue
        if any(tok in line.lower() for tok in query_tokens):
            return line[:240]
    return text[:240]


def progressive_retrieve(
    memory_root: Path,
    query: str,
    top_k: int = 3,
    recent_days: int = 7,
    episode_recent_boost: int = 2,
    episode_stale_penalty: int = 2,
    episode_decay_half_life_days: int = 3,
) -> list[RetrievedMemory]:
    query_tokens = normalize_query(query)
    entries = load_all_entries(memory_root)

    scored: list[RetrievedMemory] = []
    seen_topic_prefix: set[str] = set()

    for entry in entries:
        key_l = entry.key.lower()
        tags_l = [t.lower() for t in entry.tags]
        content_l = entry.content.lower()

        key_hit = any(tok in key_l for tok in query_tokens)
        title_tag_hit = any(tok in key_l or tok in tags_l for tok in query_tokens)
        content_hit = any(tok in content_l for tok in query_tokens)

        if query_tokens and not (key_hit or title_tag_hit or content_hit):
            continue

        score = 0.0
        if key_hit:
            score += 3
        if title_tag_hit:
            score += 2
        if content_hit:
            score += 1
        age_days = _age_days(entry.updated_at)
        if age_days is not None:
            if recent_days > 0:
                score += max(0.0, 1.0 - (age_days / float(recent_days)))
        if entry.mem_type == "episode":
            decay = exp(-float(age_days or 0) / float(episode_decay_half_life_days))
            score += (episode_recent_boost * decay) - (episode_stale_penalty * (1.0 - decay))

        topic_prefix = entry.key.split(":", 1)[0]
        if topic_prefix in seen_topic_prefix:
            score -= 1

        scored.append(RetrievedMemory(entry=entry, score=score, snippet=_snippet(entry, query_tokens)))

    scored.sort(key=lambda item: item.score, reverse=True)

    result: list[RetrievedMemory] = []
    for item in scored:
        topic_prefix = item.entry.key.split(":", 1)[0]
        if len(result) < top_k:
            result.append(item)
            seen_topic_prefix.add(topic_prefix)

    return result
