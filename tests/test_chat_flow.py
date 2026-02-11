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
