from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    name: str = "claw-cli-demo"
    timezone: str = "Asia/Shanghai"
    verbose: bool = False


class LLMConfig(BaseModel):
    provider: Literal["openai_compatible"] = "openai_compatible"
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.3
    timeout_sec: int = 60
    max_retries: int = 2


class ChatConfig(BaseModel):
    recent_turns: int = 8
    max_context_chars: int = 12000
    stream: bool = True


class MemoryConfig(BaseModel):
    root: str = "./claw_demo/memory/store"
    inject_top_k: int = 3
    grep_context_lines: int = 6
    max_item_chars: int = 1200
    enable_auto_extract: bool = True
    default_mem_type: Literal["auto", "profile", "fact", "episode"] = "auto"
    episode_retention_days: int = 14
    episode_recent_days: int = 7
    episode_recent_boost: int = 2
    episode_stale_penalty: int = 2
    episode_decay_half_life_days: int = 3
    episode_trigger_keywords: list[str] = Field(
        default_factory=lambda: [
            "进展",
            "今天做了",
            "刚完成",
            "刚遇到问题",
            "决定",
            "总结",
            "会议",
            "计划",
        ]
    )

    @field_validator("episode_retention_days", "episode_recent_days", "episode_decay_half_life_days")
    @classmethod
    def _validate_episode_days(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("episode day config must be > 0")
        return value


class SkillsConfig(BaseModel):
    enabled: list[str] = Field(
        default_factory=lambda: ["weather", "time", "file_search", "file_read", "summarize", "email"]
    )
    timeout_sec: int = 20
    max_steps: int = 6
    import_dirs: list[str] = Field(default_factory=list)


class FileAccessConfig(BaseModel):
    workspace_dir: str = ""
    allowed_roots: list[str] = Field(default_factory=lambda: ["./"])
    max_read_bytes: int = 262144


class WeatherConfig(BaseModel):
    provider: Literal["open-meteo"] = "open-meteo"
    default_city: str = "Shanghai"
    units: Literal["metric", "imperial"] = "metric"


class SMTPConfig(BaseModel):
    host: str = "smtp.example.com"
    port: int = 587
    use_ssl: bool = False
    use_tls: bool = True
    timeout: int = 30
    username: str = ""
    password: str = ""
    from_addr: str = Field(default="bot@example.com", alias="from")

    @field_validator("port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("smtp.port must be between 1 and 65535")
        return value

    @field_validator("timeout")
    @classmethod
    def _validate_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("smtp.timeout must be > 0")
        return value


class EmailConfig(BaseModel):
    enabled: bool = False
    dry_run: bool = True
    smtp: SMTPConfig = Field(default_factory=SMTPConfig)


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    chat: ChatConfig = Field(default_factory=ChatConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    file_access: FileAccessConfig = Field(default_factory=FileAccessConfig)
    weather: WeatherConfig = Field(default_factory=WeatherConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)

    @field_validator("memory")
    @classmethod
    def _validate_memory_root(cls, value: MemoryConfig) -> MemoryConfig:
        if not value.root.strip():
            raise ValueError("memory.root must not be empty")
        return value

    def resolve_memory_root(self, project_root: Path) -> Path:
        return (project_root / self.memory.root).resolve()
