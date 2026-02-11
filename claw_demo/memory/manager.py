from __future__ import annotations

from datetime import date
from pathlib import Path

from claw_demo.config.schema import Config
from claw_demo.memory.extractor import extract_memory_entry
from claw_demo.memory.grep_retriever import MemoryEntry, RetrievedMemory, progressive_retrieve
from claw_demo.memory.writer import purge_memory, upsert_entry


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
        entry = extract_memory_entry(user_text)
        if entry is None:
            return
        upsert_entry(self.memory_root, entry)
