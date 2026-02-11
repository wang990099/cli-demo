from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.memory.grep_retriever import MemoryEntry
from claw_demo.memory.manager import MemoryManager


class StubExtractor:
    def __init__(self, mapping: dict[str, list[MemoryEntry]]) -> None:
        self.mapping = mapping

    def extract(self, user_text: str, recent_messages=None) -> list[MemoryEntry]:
        return self.mapping.get(user_text, [])


class StubVerifier:
    def __init__(self, allowed_keys: set[str]) -> None:
        self.allowed_keys = allowed_keys

    def verify(self, user_text: str, entries: list[MemoryEntry], recent_messages=None) -> list[MemoryEntry]:
        return [e for e in entries if e.key in self.allowed_keys]


def _entry(key: str, mem_type: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
    return MemoryEntry(
        key=key,
        mem_type=mem_type,
        tags=tags or [mem_type],
        updated_at="2026-02-11",
        content=content,
        source_file=None,
    )


def test_progressive_memory_search(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)
    manager.add(key="project:alpha", mem_type="fact", content="用户正在做 CLI 项目", tags=["project", "cli"])
    manager.add(key="user:style", mem_type="profile", content="用户喜欢简洁回答", tags=["preference"])

    rows = manager.search("喜欢 简洁")
    assert rows
    assert "简洁" in rows[0].entry.content


def test_llm_extractor_upserts_multiple_records(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"

    stub = StubExtractor(
        {
            "我喜欢奶茶和游泳": [
                _entry("pref:beverage", "profile", "用户喜欢奶茶", ["pref", "drink"]),
                _entry("pref:hobby", "profile", "用户喜欢游泳", ["pref", "hobby"]),
            ]
        }
    )
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub)
    manager.maybe_auto_extract("我喜欢奶茶和游泳")

    rows = manager.search("喜欢")
    assert len(rows) >= 2
    joined = "\n".join(r.entry.content for r in rows)
    assert "奶茶" in joined
    assert "游泳" in joined


def test_llm_extractor_overwrites_same_key(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"

    stub = StubExtractor(
        {
            "第一次": [_entry("pref:drink", "profile", "用户喜欢咖啡", ["pref"])],
            "第二次": [_entry("pref:drink", "profile", "用户现在喜欢奶茶", ["pref"])],
        }
    )
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub)
    manager.maybe_auto_extract("第一次")
    manager.maybe_auto_extract("第二次")

    rows = manager.search("喜欢")
    assert rows
    assert "奶茶" in rows[0].entry.content
    assert "咖啡" not in rows[0].entry.content


def test_extractor_no_output_keeps_memory_unchanged(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"

    stub = StubExtractor({"无记忆价值": []})
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub)
    manager.add("project:seed", "fact", "初始事实", ["seed"])
    manager.maybe_auto_extract("无记忆价值")

    rows = manager.search("初始")
    assert rows
    assert rows[0].entry.key == "project:seed"


def test_verify_stage_filters_proposed_records(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    stub_extractor = StubExtractor(
        {
            "输入": [
                _entry("pref:drink", "profile", "用户喜欢奶茶", ["pref"]),
                _entry("noise:tmp", "fact", "哈", ["noise"]),
            ]
        }
    )
    stub_verifier = StubVerifier({"pref:drink"})
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub_extractor, verifier=stub_verifier)
    manager.maybe_auto_extract("输入")
    rows = manager.search("喜欢")
    assert rows
    assert rows[0].entry.key == "pref:drink"
    assert all(r.entry.key != "noise:tmp" for r in rows)
