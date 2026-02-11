from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.memory.grep_retriever import MemoryEntry
from claw_demo.memory.manager import MemoryManager
from claw_demo.memory.writer import upsert_entry


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
    joined = "\n".join(item.entry.content for item in rows)
    assert "奶茶" in joined


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
    assert rows[0].entry.key.startswith("pref:like:")
    assert all(r.entry.key != "noise:tmp" for r in rows)


def test_episode_trigger_forces_episode_mem_type(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    stub = StubExtractor(
        {
            "今天做了接口联调，进展不错": [
                _entry("work:update", "fact", "今天完成接口联调", ["work"]),
            ]
        }
    )
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub)
    manager.maybe_auto_extract("今天做了接口联调，进展不错")

    episode_files = list((tmp_path / "memory" / "episodes").glob("*-episode.md"))
    assert episode_files
    text = episode_files[0].read_text(encoding="utf-8")
    assert "- type: episode" in text
    assert "今天完成接口联调" in text


def test_episode_retention_cleanup_on_manager_init(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.memory.episode_retention_days = 1

    episodes = tmp_path / "memory" / "episodes"
    episodes.mkdir(parents=True, exist_ok=True)
    (episodes / "2000-01-01-episode.md").write_text("## old\n- type: episode\n", encoding="utf-8")
    (episodes / "2999-01-01-episode.md").write_text("## future\n- type: episode\n", encoding="utf-8")

    MemoryManager(config=cfg, project_root=tmp_path)
    assert not (episodes / "2000-01-01-episode.md").exists()
    assert (episodes / "2999-01-01-episode.md").exists()


def test_recent_episode_scores_higher_than_fact(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.memory.episode_recent_boost = 3

    manager = MemoryManager(config=cfg, project_root=tmp_path)
    upsert_entry(
        tmp_path / "memory",
        _entry("fact:status", "fact", "项目进展稳定，今天完成修复", ["project"]),
    )
    upsert_entry(
        tmp_path / "memory",
        _entry("episode:today", "episode", "今天完成修复并总结问题", ["project"]),
    )

    rows = manager.search("今天 完成 修复")
    assert rows
    assert rows[0].entry.mem_type == "episode"


def test_episode_decay_prefers_newer_episode(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.memory.episode_decay_half_life_days = 3
    cfg.memory.episode_recent_boost = 4
    cfg.memory.episode_stale_penalty = 2

    manager = MemoryManager(config=cfg, project_root=tmp_path)
    upsert_entry(
        tmp_path / "memory",
        MemoryEntry(
            key="episode:new",
            mem_type="episode",
            tags=["project"],
            updated_at="2026-02-11",
            content="今天完成联调并总结问题",
            source_file=None,
        ),
    )
    upsert_entry(
        tmp_path / "memory",
        MemoryEntry(
            key="episode:old",
            mem_type="episode",
            tags=["project"],
            updated_at="2026-01-20",
            content="今天完成联调并总结问题",
            source_file=None,
        ),
    )

    rows = manager.search("今天 完成 联调 总结")
    assert rows
    assert rows[0].entry.key == "episode:new"


def test_profile_repair_merges_preference_conflicts(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    profile = tmp_path / "memory" / "profile.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        (
            "## beverage_preference\n"
            "- type: profile\n"
            "- tags: 喜好,饮品\n"
            "- updated_at: 2026-02-11\n"
            "- content: 喜欢咖啡\n"
            "## user_hobby_coffee\n"
            "- type: profile\n"
            "- tags: 喜好,饮品\n"
            "- updated_at: 2026-02-11T08:00:01\n"
            "- content: 不再喜欢咖啡\n"
            "## user_preference_drink\n"
            "- type: profile\n"
            "- tags: 喜好,饮品\n"
            "- updated_at: 2026-02-11T09:00:01\n"
            "- content: 喜欢奶茶\n"
            "## user_preference_sport\n"
            "- type: profile\n"
            "- tags: 喜好,运动\n"
            "- updated_at: 2026-02-11T09:10:01\n"
            "- content: 喜欢游泳\n"
        ),
        encoding="utf-8",
    )

    MemoryManager(config=cfg, project_root=tmp_path)
    repaired = profile.read_text(encoding="utf-8")
    assert "pref:dislike:咖啡" in repaired
    assert "pref:like:奶茶" in repaired
    assert "pref:like:游泳" in repaired
    assert "## beverage_preference" not in repaired
    assert "- content: 喜欢咖啡" not in repaired


def test_updated_at_written_with_second_precision(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)
    manager.add(key="k", mem_type="fact", content="v")
    text = (tmp_path / "memory" / "facts.md").read_text(encoding="utf-8")
    assert "updated_at: " in text
    assert "T" in text
    assert len([line for line in text.splitlines() if line.startswith("- updated_at: ")][0].split(": ", 1)[1]) >= 19


def test_index_rebuild_removes_stale_keys_after_profile_repair(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    profile = tmp_path / "memory" / "profile.md"
    index = tmp_path / "memory" / "index" / "memory_keys.tsv"
    profile.parent.mkdir(parents=True, exist_ok=True)
    index.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(
        (
            "## old_pref_key\n"
            "- type: profile\n"
            "- tags: 喜好\n"
            "- updated_at: 2026-02-11\n"
            "- content: 喜欢奶茶\n"
        ),
        encoding="utf-8",
    )
    index.write_text("old_pref_key\tprofile.md\n", encoding="utf-8")

    MemoryManager(config=cfg, project_root=tmp_path)
    rebuilt = index.read_text(encoding="utf-8")
    assert "old_pref_key" not in rebuilt
    assert "pref:like:奶茶\tprofile.md" in rebuilt


def test_preference_sentence_with_like_and_dislike_extracts_both(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"

    stub = StubExtractor({"我现在不喜欢咖啡了，我现在喜欢奶茶": []})
    manager = MemoryManager(config=cfg, project_root=tmp_path, extractor=stub)
    manager.maybe_auto_extract("我现在不喜欢咖啡了，我现在喜欢奶茶")

    rows = manager.search("喜欢")
    joined = "\n".join(item.entry.content for item in rows)
    assert "不喜欢咖啡" in joined
    assert "喜欢奶茶" in joined


def test_preference_conflict_same_second_keeps_latest_statement(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)
    manager.add("a", "profile", "喜欢咖啡", ["爱好", "饮品"])
    manager.maybe_auto_extract("我现在不喜欢咖啡了")

    rows = manager.search("咖啡")
    assert rows
    joined = "\n".join(item.entry.content for item in rows)
    assert "不喜欢咖啡" in joined
