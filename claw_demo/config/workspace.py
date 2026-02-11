from __future__ import annotations

from pathlib import Path

from claw_demo.config.schema import Config


def default_workspace_dir(run_dir: Path) -> Path:
    return (run_dir.resolve().parent / "workspace").resolve()


def resolve_workspace_dir(config: Config, run_dir: Path) -> Path:
    raw = (config.file_access.workspace_dir or "").strip()
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (run_dir / path).resolve()
        else:
            path = path.resolve()
    else:
        path = default_workspace_dir(run_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_workspace_to_env(env_path: Path, workspace_dir: Path) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    key = "WORKSPACE_DIR"
    value = str(workspace_dir.resolve())
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)

    if not replaced:
        out.append(f"{key}={value}")

    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
