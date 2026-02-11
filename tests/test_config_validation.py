from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config


def test_load_default_config() -> None:
    cfg = load_config()
    assert cfg.llm.model
    assert cfg.skills.timeout_sec > 0
    assert cfg.memory.default_mem_type in {"auto", "profile", "fact", "episode"}
    assert cfg.memory.episode_retention_days > 0
    assert cfg.memory.episode_recent_days > 0
    assert cfg.memory.episode_decay_half_life_days > 0
    assert cfg.memory.episode_trigger_keywords


def test_env_substitution(tmp_path: Path, monkeypatch) -> None:
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        """
llm:
  api_key: ${OPENAI_API_KEY}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "abc123")
    cfg = load_config(cfg_file)
    assert cfg.llm.api_key == "abc123"


def test_dotenv_substitution(tmp_path: Path, monkeypatch) -> None:
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        """
llm:
  api_key: ${OPENAI_API_KEY}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from_dotenv\n", encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    cfg = load_config(cfg_file)
    assert cfg.llm.api_key == "from_dotenv"


def test_email_smtp_fields_and_from_env(tmp_path: Path, monkeypatch) -> None:
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(
        """
email:
  smtp:
    host: smtp.163.com
    port: 465
    use_ssl: true
    use_tls: true
    timeout: 30
    from: ${SMTP_FROM}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SMTP_FROM", "bot@163.com")
    cfg = load_config(cfg_file)
    assert cfg.email.smtp.host == "smtp.163.com"
    assert cfg.email.smtp.port == 465
    assert cfg.email.smtp.use_ssl is True
    assert cfg.email.smtp.use_tls is True
    assert cfg.email.smtp.timeout == 30
    assert cfg.email.smtp.from_addr == "bot@163.com"
