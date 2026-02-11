from __future__ import annotations

import re
from datetime import datetime
from hashlib import sha1

from claw_demo.memory.grep_retriever import MemoryEntry


_DISLIKE_RE = re.compile(r"(?:不再喜欢|不喜欢|讨厌)\s*([^\s，。；;！!？?]+)")
_LIKE_RE = re.compile(r"(?:喜欢|偏好|爱好)\s*([^\s，。；;！!？?]+)")
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CLAUSE_SPLIT_RE = re.compile(r"[，,。；;！!？?\n]+")
_ITEM_SPLIT_RE = re.compile(r"[、/]|(?:和|及|与|跟)")
_TRAILING_PARTICLE_RE = re.compile(r"[了吧吗呀啊呢嘛]$")
_LEADING_NOISE_RE = re.compile(r"^(?:我|现在|目前|已经|还是|也|还|更|最|都|就|是|的)+")
_PREF_STOPWORDS = {"什么", "这个", "那个", "东西", "事情"}


def now_ts() -> str:
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


def normalize_updated_at(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return now_ts()
    if _DATE_ONLY_RE.match(raw):
        return f"{raw}T00:00:00"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt.replace(microsecond=0).isoformat(timespec="seconds")
    except ValueError:
        return now_ts()


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        item = tag.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _ts_dt(value: str) -> datetime:
    ts = normalize_updated_at(value)
    return datetime.fromisoformat(ts)


def _safe_pref_token(item: str) -> str:
    token = re.sub(r"[^\w\u4e00-\u9fff]+", "_", item.strip().lower()).strip("_")
    if token:
        return token
    return sha1(item.encode("utf-8")).hexdigest()[:10]


def _extract_preference(content: str) -> tuple[str, str] | None:
    text = content.strip()
    if not text:
        return None
    m_dislike = _DISLIKE_RE.search(text)
    if m_dislike:
        return ("dislike", m_dislike.group(1).strip())
    m_like = _LIKE_RE.search(text)
    if m_like:
        return ("like", m_like.group(1).strip())
    return None


def canonicalize_profile_entry(entry: MemoryEntry) -> tuple[MemoryEntry, str | None]:
    normalized = MemoryEntry(
        key=entry.key.strip(),
        mem_type="profile",
        tags=normalize_tags(entry.tags),
        updated_at=normalize_updated_at(entry.updated_at),
        content=entry.content.strip(),
        source_file=entry.source_file,
    )
    pref = _extract_preference(normalized.content)
    if pref is None:
        if not normalized.tags:
            normalized.tags = ["profile"]
        return normalized, None

    polarity, item = pref
    key = f"pref:{polarity}:{_safe_pref_token(item)}"
    content = f"{'喜欢' if polarity == 'like' else '不喜欢'}{item}"
    tags = normalize_tags(normalized.tags + ["pref", polarity])
    return (
        MemoryEntry(
            key=key,
            mem_type="profile",
            tags=tags,
            updated_at=normalized.updated_at,
            content=content,
            source_file=normalized.source_file,
        ),
        _safe_pref_token(item),
    )


def merge_profile_entries(entries: list[MemoryEntry]) -> list[MemoryEntry]:
    pref_by_item: dict[str, MemoryEntry] = {}
    other_by_key: dict[str, MemoryEntry] = {}

    for entry in entries:
        normalized, pref_item = canonicalize_profile_entry(entry)
        if pref_item is not None:
            current = pref_by_item.get(pref_item)
            if current is None or _ts_dt(normalized.updated_at) >= _ts_dt(current.updated_at):
                pref_by_item[pref_item] = normalized
            continue

        if not normalized.key:
            continue
        current = other_by_key.get(normalized.key)
        if current is None or _ts_dt(normalized.updated_at) >= _ts_dt(current.updated_at):
            other_by_key[normalized.key] = normalized

    merged = list(other_by_key.values()) + list(pref_by_item.values())
    merged.sort(key=lambda item: item.key)
    return merged


def merge_entries_by_key(entries: list[MemoryEntry], mem_type: str) -> list[MemoryEntry]:
    latest_by_key: dict[str, MemoryEntry] = {}
    for entry in entries:
        normalized = MemoryEntry(
            key=entry.key.strip(),
            mem_type=mem_type,
            tags=normalize_tags(entry.tags),
            updated_at=normalize_updated_at(entry.updated_at),
            content=entry.content.strip(),
            source_file=entry.source_file,
        )
        if not normalized.key:
            continue
        current = latest_by_key.get(normalized.key)
        if current is None or _ts_dt(normalized.updated_at) >= _ts_dt(current.updated_at):
            latest_by_key[normalized.key] = normalized
    merged = list(latest_by_key.values())
    merged.sort(key=lambda item: item.key)
    return merged


def _clean_pref_item(raw: str) -> str:
    item = raw.strip()
    item = _TRAILING_PARTICLE_RE.sub("", item)
    item = _LEADING_NOISE_RE.sub("", item)
    item = item.strip("：:，,。；;！!？? ")
    return item


def _extract_preferences_from_clause(clause: str) -> list[tuple[str, str]]:
    text = clause.strip()
    if not text:
        return []

    polarity = ""
    marker = ""
    if "不再喜欢" in text:
        polarity, marker = "dislike", "不再喜欢"
    elif "不喜欢" in text:
        polarity, marker = "dislike", "不喜欢"
    elif "讨厌" in text:
        polarity, marker = "dislike", "讨厌"
    elif "喜欢" in text:
        polarity, marker = "like", "喜欢"
    elif "偏好" in text:
        polarity, marker = "like", "偏好"
    elif "爱好" in text:
        polarity, marker = "like", "爱好"
    if not polarity:
        return []

    tail = text.split(marker, 1)[1].strip()
    candidates = _ITEM_SPLIT_RE.split(tail)
    out: list[tuple[str, str]] = []
    for c in candidates:
        item = _clean_pref_item(c)
        if len(item) < 1 or item in _PREF_STOPWORDS:
            continue
        out.append((polarity, item))
    return out


def extract_preference_entries(user_text: str, updated_at: str | None = None) -> list[MemoryEntry]:
    ts = normalize_updated_at(updated_at or now_ts())
    seen: set[tuple[str, str]] = set()
    entries: list[MemoryEntry] = []

    for clause in _CLAUSE_SPLIT_RE.split(user_text):
        for polarity, item in _extract_preferences_from_clause(clause):
            k = (polarity, item)
            if k in seen:
                continue
            seen.add(k)
            token = _safe_pref_token(item)
            entries.append(
                MemoryEntry(
                    key=f"pref:{polarity}:{token}",
                    mem_type="profile",
                    tags=["pref", polarity, "爱好"],
                    updated_at=ts,
                    content=f"{'喜欢' if polarity == 'like' else '不喜欢'}{item}",
                    source_file=None,
                )
            )
    return entries
