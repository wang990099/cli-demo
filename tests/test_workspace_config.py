from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.config.workspace import default_workspace_dir, resolve_workspace_dir, write_workspace_to_env


def test_default_workspace_is_sibling(tmp_path: Path) -> None:
    run_dir = tmp_path / "project"
    run_dir.mkdir(parents=True)
    assert default_workspace_dir(run_dir) == (tmp_path / "workspace").resolve()


def test_resolve_workspace_from_config(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.file_access.workspace_dir = "./myws"
    ws = resolve_workspace_dir(cfg, tmp_path)
    assert ws == (tmp_path / "myws").resolve()
    assert ws.exists()


def test_write_workspace_to_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=abc\n", encoding="utf-8")
    ws = (tmp_path / "workspace").resolve()
    write_workspace_to_env(env_path, ws)
    content = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=abc" in content
    assert f"WORKSPACE_DIR={ws}" in content
