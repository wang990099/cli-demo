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
