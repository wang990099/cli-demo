from __future__ import annotations

from datetime import date
from pathlib import Path

from claw_demo.config.schema import Config
from claw_demo.memory.episode import is_episode_trigger, prune_old_episode_files
from claw_demo.memory.extractor import LLMMemoryExtractor, LLMMemoryVerifier, MemoryExtractor, MemoryVerifier
from claw_demo.memory.grep_retriever import MemoryEntry, RetrievedMemory, progressive_retrieve
from claw_demo.memory.writer import purge_memory, upsert_entry


class MemoryManager:
    def __init__(
        self,
        config: Config,
        project_root: Path,
        extractor: MemoryExtractor | None = None,
        verifier: MemoryVerifier | None = None,
    ) -> None:
        self.config = config
        self.memory_root = (project_root / config.memory.root).resolve()
        self.extractor = extractor or LLMMemoryExtractor(config)
        self.verifier = verifier or LLMMemoryVerifier(config)
        (self.memory_root / "episodes").mkdir(parents=True, exist_ok=True)
        (self.memory_root / "index").mkdir(parents=True, exist_ok=True)
        for p in [self.memory_root / "profile.md", self.memory_root / "facts.md", self.memory_root / "index" / "memory_keys.tsv"]:
            if not p.exists():
                p.write_text("", encoding="utf-8")
        self._cleanup_episodes()

    def search(self, query: str) -> list[RetrievedMemory]:
        self._cleanup_episodes()
        return progressive_retrieve(
            self.memory_root,
            query,
            top_k=self.config.memory.inject_top_k,
            recent_days=self.config.memory.episode_recent_days,
            episode_recent_boost=self.config.memory.episode_recent_boost,
            episode_stale_penalty=self.config.memory.episode_stale_penalty,
            episode_decay_half_life_days=self.config.memory.episode_decay_half_life_days,
        )

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

    def maybe_auto_extract(
        self,
        user_text: str,
        recent_messages: list[dict[str, str]] | None = None,
        mem_type_override: str | None = None,
    ) -> None:
        if not self.config.memory.enable_auto_extract:
            return
        self._cleanup_episodes()
        proposed = self.extractor.extract(user_text, recent_messages=recent_messages)
        approved = self.verifier.verify(user_text, proposed, recent_messages=recent_messages)
        effective_override = self._effective_mem_type_override(user_text, mem_type_override)
        if effective_override:
            approved = [
                MemoryEntry(
                    key=item.key,
                    mem_type=effective_override,
                    tags=item.tags,
                    updated_at=item.updated_at,
                    content=item.content,
                    source_file=item.source_file,
                )
                for item in approved
            ]
        for entry in approved:
            upsert_entry(self.memory_root, entry)

    def _effective_mem_type_override(self, user_text: str, mem_type_override: str | None) -> str | None:
        if mem_type_override and mem_type_override != "auto":
            return mem_type_override
        if is_episode_trigger(user_text, self.config.memory.episode_trigger_keywords):
            return "episode"
        return None

    def _cleanup_episodes(self) -> None:
        prune_old_episode_files(
            memory_root=self.memory_root,
            retention_days=self.config.memory.episode_retention_days,
        )
