from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from claw_demo.config.schema import Config

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            return os.getenv(match.group(1), "")

        return _ENV_RE.sub(repl, value)
    return value


def load_config(config_path: Path | None = None) -> Config:
    if config_path is None:
        config_path = Path(__file__).with_name("default.yaml")
    # Load dotenv from config directory and current working directory.
    # Do not override values already provided by process environment.
    candidates = [config_path.parent / ".env", Path.cwd() / ".env"]
    seen: set[Path] = set()
    for dotenv_path in candidates:
        resolved = dotenv_path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            load_dotenv(resolved, override=False)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    substituted = _substitute_env(raw)
    return Config.model_validate(substituted)
