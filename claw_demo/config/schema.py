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


class SkillsConfig(BaseModel):
    enabled: list[str] = Field(default_factory=lambda: ["weather", "file_search", "file_read", "summarize", "email"])
    timeout_sec: int = 20


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
    username: str = ""
    password: str = ""
    from_addr: str = Field(default="bot@example.com", alias="from")


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
