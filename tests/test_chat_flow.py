from __future__ import annotations

from pathlib import Path

from claw_demo.chat.engine import ChatEngine
from claw_demo.config.loader import load_config
from claw_demo.memory.grep_retriever import MemoryEntry


class StubExtractor:
    def __init__(self, mapping: dict[str, list[MemoryEntry]]) -> None:
        self.mapping = mapping

    def extract(self, user_text: str, recent_messages=None) -> list[MemoryEntry]:
        return self.mapping.get(user_text, [])


def _entry(key: str, mem_type: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
    return MemoryEntry(
        key=key,
        mem_type=mem_type,
        tags=tags or [mem_type],
        updated_at="2026-02-11",
        content=content,
        source_file=None,
    )


def test_chat_skill_roundtrip(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    out = engine.handle_user_input("请读文件 README.md")
    assert "hello" in out


def test_auto_memory_extract_with_injected_llm_extractor(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.memory.extractor = StubExtractor(
        {
            "我喜欢奶茶": [_entry("pref:drink", "profile", "用户喜欢奶茶", ["pref", "drink"])],
            "我还喜欢游泳": [_entry("pref:hobby", "profile", "用户喜欢游泳", ["pref", "hobby"])],
        }
    )

    engine.handle_user_input("我喜欢奶茶")
    engine.handle_user_input("我还喜欢游泳")
    rows = engine.memory.search("喜欢")
    assert rows
    text = "\n".join(item.entry.content for item in rows)
    assert "奶茶" in text
    assert "游泳" in text


def test_reset_does_not_drop_long_term_memory(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.memory.extractor = StubExtractor(
        {
            "记住我喜欢奶茶": [_entry("pref:drink", "profile", "用户喜欢奶茶", ["pref"])],
        }
    )
    engine.handle_user_input("记住我喜欢奶茶")
    res = engine._handle_slash("/reset")
    assert res.handled

    rows = engine.memory.search("喜欢")
    assert rows
    assert "奶茶" in rows[0].entry.content


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
