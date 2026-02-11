from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config
from claw_demo.skills.dispatcher import AgentSkillDispatcher
from claw_demo.skills.models import SkillContext
from claw_demo.skills.toolbox import ToolExecutor


def test_dispatch_requires_llm(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    cfg.file_access.workspace_dir = str(tmp_path)

    dispatcher = AgentSkillDispatcher(config=cfg, project_root=tmp_path)
    result = dispatcher.dispatch("file_read", request_text="读 README.md")
    assert not result.ok
    assert "LLM 不可用" in result.text


def test_skill_manifest_loading_and_check_report() -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    dispatcher = AgentSkillDispatcher(config=cfg, project_root=Path.cwd())
    skills = dispatcher.enabled_skills()
    assert "weather" in skills
    assert "file_search" in skills

    reports = dispatcher.health_check_detailed()
    assert reports["weather"].status == "error"
    assert "llm unavailable for agent-skill execution" in reports["weather"].issues


def test_tool_executor_file_read_blocks_outside_root(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.file_access.allowed_roots = ["./safe"]
    (tmp_path / "safe").mkdir(parents=True, exist_ok=True)
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")

    executor = ToolExecutor()
    ctx = SkillContext(config=cfg, project_root=tmp_path, workspace_root=tmp_path)
    result = executor.execute("file_read", {"path": "outside.txt"}, ctx)
    assert not result.ok
    assert "允许范围" in result.text


def test_tool_executor_email_dry_run(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.email.enabled = False
    cfg.email.dry_run = True
    cfg.email.smtp.host = "smtp.163.com"
    cfg.email.smtp.port = 465
    cfg.email.smtp.use_ssl = True
    cfg.email.smtp.use_tls = True
    cfg.email.smtp.from_addr = "bot@163.com"

    executor = ToolExecutor()
    ctx = SkillContext(config=cfg, project_root=Path.cwd(), workspace_root=tmp_path)
    result = executor.execute("email", {"to": "a@b.com", "subject": "s", "body": "b"}, ctx)
    assert result.ok
    assert "DRY-RUN" in result.text
    assert "smtp.163.com:465" in result.text
    assert "from=bot@163.com" in result.text
    assert "已忽略 use_tls" in result.text


def test_external_agent_skill_import(tmp_path: Path) -> None:
    ext_root = tmp_path / "ext_skills"
    custom_dir = ext_root / "agents" / "custom_echo"
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "SKILL.md").write_text(
        """name: custom_echo
description: 外部自定义技能

你是外部导入的技能。
""",
        encoding="utf-8",
    )

    cfg = load_config()
    cfg.llm.api_key = ""
    cfg.skills.import_dirs = [str(ext_root)]
    cfg.skills.enabled.append("custom_echo")

    dispatcher = AgentSkillDispatcher(config=cfg, project_root=Path.cwd())
    assert "custom_echo" in dispatcher.enabled_skills()
    report = dispatcher.health_check_detailed()["custom_echo"]
    assert any("external source:" in item for item in report.runtime)
