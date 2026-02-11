from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claw_demo.config.schema import Config


@dataclass
class SkillContext:
    config: Config
    project_root: Path
    workspace_root: Path


@dataclass
class SkillResult:
    ok: bool
    text: str
    data: dict[str, Any] | None = None


@dataclass
class AgentSkillSpec:
    name: str
    description: str
    instructions: str
    directory_name: str
    source_path: Path
