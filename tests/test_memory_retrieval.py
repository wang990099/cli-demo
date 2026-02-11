from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.memory.manager import MemoryManager


def test_progressive_memory_search(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)
    manager.add(key="project:alpha", mem_type="fact", content="用户正在做 CLI 项目", tags=["project", "cli"])
    manager.add(key="pref:style", mem_type="profile", content="用户喜欢简洁回答", tags=["pref"])

    rows = manager.search("喜欢 简洁")
    assert rows
    assert rows[0].entry.key.startswith("pref:")


def test_preference_query_after_reset_like_dislike(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)

    manager.maybe_auto_extract("我喜欢咖啡")
    manager.maybe_auto_extract("我现在喜欢奶茶了，不喜欢咖啡了")

    like_rows = manager.search("我喜欢什么")
    dislike_rows = manager.search("我不喜欢什么")

    assert like_rows
    assert dislike_rows
    assert like_rows[0].entry.key == "pref:like"
    assert "奶茶" in like_rows[0].entry.content
    assert "奶茶" in like_rows[0].snippet
    assert "pref:like" not in like_rows[0].snippet
    assert dislike_rows[0].entry.key == "pref:dislike"
    assert "咖啡" in dislike_rows[0].entry.content
    assert "咖啡" in dislike_rows[0].snippet
    assert "pref:dislike" not in dislike_rows[0].snippet


def test_preference_like_items_accumulate(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)

    manager.maybe_auto_extract("我喜欢奶茶")
    manager.maybe_auto_extract("我还喜欢游泳")

    like_rows = manager.search("我喜欢什么")
    assert like_rows
    top = like_rows[0]
    assert top.entry.key == "pref:like"
    assert "奶茶" in top.entry.content
    assert "游泳" in top.entry.content


def test_preference_conflict_resolution(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)

    manager.maybe_auto_extract("我喜欢咖啡")
    manager.maybe_auto_extract("我现在喜欢奶茶了，不喜欢咖啡了")

    like_rows = manager.search("我喜欢什么")
    dislike_rows = manager.search("我不喜欢什么")
    assert like_rows and dislike_rows
    assert "奶茶" in like_rows[0].entry.content
    assert "咖啡" not in like_rows[0].entry.content
    assert "咖啡" in dislike_rows[0].entry.content


def test_preference_multi_item_phrase_split(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    manager = MemoryManager(config=cfg, project_root=tmp_path)

    manager.maybe_auto_extract("我喜欢奶茶和游泳")
    like_rows = manager.search("我喜欢什么")
    assert like_rows
    content = like_rows[0].entry.content
    assert "奶茶" in content
    assert "游泳" in content
