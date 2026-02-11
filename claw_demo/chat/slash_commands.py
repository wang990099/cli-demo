from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SlashResult:
    handled: bool
    should_exit: bool = False
    output: str = ""
    dryrun_override: bool | None = None
    reset_history: bool = False


def parse_slash(user_input: str) -> tuple[str, str | None]:
    parts = user_input.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None
    return cmd, arg
