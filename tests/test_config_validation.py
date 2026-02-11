from __future__ import annotations

from pathlib import Path

from claw_demo.config.loader import load_config


def test_load_default_config() -> None:
    cfg = load_config()
    assert cfg.llm.model
    assert cfg.skills.timeout_sec > 0


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
