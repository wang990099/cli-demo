from __future__ import annotations

from datetime import date
from pathlib import Path

from claw_demo.config.schema import Config
from claw_demo.memory.extractor import extract_memory, format_pref_content, parse_pref_items
from claw_demo.memory.grep_retriever import MemoryEntry, RetrievedMemory, load_all_entries, progressive_retrieve
from claw_demo.memory.writer import delete_entry, purge_memory, upsert_entry


class MemoryManager:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.memory_root = (project_root / config.memory.root).resolve()
        (self.memory_root / "episodes").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "index").mkdir(parents=True, exist_ok=True)
        for p in [self.memory_root / "profile.md", self.memory_root / "facts.md", self.memory_root / "index" / "memory_keys.tsv"]:
            if not p.exists():
                p.write_text("", encoding="utf-8")

    def search(self, query: str) -> list[RetrievedMemory]:
        return progressive_retrieve(self.memory_root, query, top_k=self.config.memory.inject_top_k)

    def add(self, key: str, mem_type: str, content: str, tags: list[str] | None = None) -> None:
        entry = MemoryEntry(
            key=key,
            mem_type=mem_type,
            tags=tags or [mem_type],
            updated_at=date.today().isoformat(),
            content=content,
            source_file=self.memory_root,
        )
        upsert_entry(self.memory_root, entry)

    def purge(self, scope: str) -> None:
        purge_memory(self.memory_root, scope)

    def maybe_auto_extract(self, user_text: str) -> None:
        if not self.config.memory.enable_auto_extract:
            return
        extracted = extract_memory(user_text)
        self._apply_preference_updates(extracted.likes, extracted.dislikes)
        for entry in extracted.additional_entries:
            upsert_entry(self.memory_root, entry)

    def _apply_preference_updates(self, new_likes: list[str], new_dislikes: list[str]) -> None:
        if not new_likes and not new_dislikes:
            return

        existing = load_all_entries(self.memory_root)
        like_items: list[str] = []
        dislike_items: list[str] = []
        for entry in existing:
            if entry.key == "pref:like":
                like_items = parse_pref_items(entry.content)
            elif entry.key == "pref:dislike":
                dislike_items = parse_pref_items(entry.content)

        for item in new_likes:
            if item not in like_items:
                like_items.append(item)
            if item in dislike_items:
                dislike_items.remove(item)

        for item in new_dislikes:
            if item not in dislike_items:
                dislike_items.append(item)
            if item in like_items:
                like_items.remove(item)

        today = date.today().isoformat()
        if like_items:
            upsert_entry(
                self.memory_root,
                MemoryEntry(
                    key="pref:like",
                    mem_type="profile",
                    tags=["pref", "like", "auto"],
                    updated_at=today,
                    content=format_pref_content("like", like_items),
                    source_file=None,
                ),
            )
        else:
            delete_entry(self.memory_root, key="pref:like", mem_type="profile")

        if dislike_items:
            upsert_entry(
                self.memory_root,
                MemoryEntry(
                    key="pref:dislike",
                    mem_type="profile",
                    tags=["pref", "dislike", "auto"],
                    updated_at=today,
                    content=format_pref_content("dislike", dislike_items),
                    source_file=None,
                ),
            )
        else:
            delete_entry(self.memory_root, key="pref:dislike", mem_type="profile")
