from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.skills.dispatcher import SkillDispatcher


def test_file_read_blocks_outside_root(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.file_access.allowed_roots = ["./safe"]
    (tmp_path / "safe").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    dispatcher = SkillDispatcher(config=cfg, project_root=tmp_path)
    result = dispatcher.dispatch("file_read", {"path": "outside.txt"})
    assert not result.ok
    assert "允许范围" in result.text


def test_email_dry_run(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.email.enabled = False
    cfg.email.dry_run = True
    cfg.email.smtp.host = "smtp.163.com"
    cfg.email.smtp.port = 465
    cfg.email.smtp.use_ssl = True
    cfg.email.smtp.use_tls = True
    cfg.email.smtp.from_addr = "bot@163.com"
    dispatcher = SkillDispatcher(config=cfg, project_root=Path.cwd())
    result = dispatcher.dispatch("email", {"to": "a@b.com", "subject": "s", "body": "b"})
    assert result.ok
    assert "DRY-RUN" in result.text
    assert "smtp.163.com:465" in result.text
    assert "from=bot@163.com" in result.text
    assert "已忽略 use_tls" in result.text
