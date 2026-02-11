from __future__ import annotations

from pathlib import Path

from claw_demo.chat.engine import ChatEngine
from claw_demo.config.loader import load_config


def test_chat_skill_roundtrip(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    out = engine.handle_user_input("请读文件 README.md")
    assert "hello" in out


def test_auto_memory_extract(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.handle_user_input("我喜欢简洁回答")
    rows = engine.memory.search("喜欢")
    assert rows


def test_auto_memory_extract_preference_update(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.handle_user_input("我喜欢咖啡")
    engine.handle_user_input("我现在喜欢奶茶了，不喜欢咖啡了")
    like_rows = engine.memory.search("我喜欢什么")
    dislike_rows = engine.memory.search("我不喜欢什么")
    assert like_rows and like_rows[0].entry.key == "pref:like"
    assert "奶茶" in like_rows[0].entry.content
    assert dislike_rows and dislike_rows[0].entry.key == "pref:dislike"


def test_reset_does_not_drop_long_term_preferences(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.handle_user_input("我喜欢奶茶")
    engine.handle_user_input("我还喜欢游泳")
    res = engine._handle_slash("/reset")
    assert res.handled
    like_rows = engine.memory.search("我喜欢什么")
    assert like_rows
    assert "奶茶" in like_rows[0].entry.content
    assert "游泳" in like_rows[0].entry.content


def test_chat_stream_writer(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    cfg.chat.stream = True
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    chunks: list[str] = []
    final = engine.handle_user_input(
        "请读文件 README.md",
        stream_writer=lambda chunk: chunks.append(chunk),
    )
    assert chunks
    assert "".join(chunks) == final
    assert "hello" in final


def test_stream_slash_toggle(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    cfg.chat.stream = True

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    off = engine._handle_slash("/stream off")
    assert off.handled
    assert engine.config.chat.stream is False
    on = engine._handle_slash("/stream on")
    assert on.handled
    assert engine.config.chat.stream is True


def test_help_slash_command(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    res = engine._handle_slash("/help")
    assert res.handled
    assert "/exit" in res.output
    assert "/stream on|off" in res.output
