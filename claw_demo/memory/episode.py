from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path


_EPISODE_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-episode\.md$")


def is_episode_trigger(text: str, keywords: list[str]) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return False
    for keyword in keywords:
        kw = keyword.strip().lower()
        if kw and kw in lowered:
            return True
    return False


def prune_old_episode_files(memory_root: Path, retention_days: int, today: date | None = None) -> int:
    episodes_dir = memory_root / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    base_day = today or date.today()
    cutoff = base_day - timedelta(days=retention_days)
    deleted = 0

    for path in episodes_dir.glob("*-episode.md"):
        matched = _EPISODE_FILE_RE.match(path.name)
        if not matched:
            continue
        try:
            file_day = date.fromisoformat(matched.group(1))
        except ValueError:
            continue
        if file_day < cutoff:
            path.unlink(missing_ok=True)
            deleted += 1
    return deleted
