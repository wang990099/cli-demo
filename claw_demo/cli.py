from __future__ import annotations

from pathlib import Path

import typer

from claw_demo.chat.engine import ChatEngine
from claw_demo.config.loader import load_config
from claw_demo.config.workspace import resolve_workspace_dir, write_workspace_to_env
from claw_demo.memory.manager import MemoryManager
from claw_demo.skills.dispatcher import AgentSkillDispatcher

app = typer.Typer(help="Claw CLI Demo")
mem_app = typer.Typer(help="Memory commands")
skill_app = typer.Typer(help="Skill commands")
workspace_app = typer.Typer(help="Workspace commands")
app.add_typer(mem_app, name="mem")
app.add_typer(skill_app, name="skill")
app.add_typer(workspace_app, name="workspace")


def _ctx() -> tuple[Path, object]:
    project_root = Path.cwd()
    cfg = load_config()
    return project_root, cfg


@app.command()
def chat() -> None:
    project_root, cfg = _ctx()
    engine = ChatEngine(config=cfg, project_root=project_root)
    engine.run_loop()


@mem_app.command("search")
def mem_search(query: str) -> None:
    project_root, cfg = _ctx()
    manager = MemoryManager(config=cfg, project_root=project_root)
    items = manager.search(query)
    if not items:
        typer.echo("无结果")
        return
    for item in items:
        typer.echo(f"[{item.score}] {item.entry.key} -> {item.snippet}")


@mem_app.command("add")
def mem_add(key: str, mem_type: str = typer.Option("fact", "--type"), content: str = typer.Option(..., "--content")) -> None:
    project_root, cfg = _ctx()
    manager = MemoryManager(config=cfg, project_root=project_root)
    manager.add(key=key, mem_type=mem_type, content=content)
    typer.echo("ok")


@mem_app.command("purge")
def mem_purge(scope: str = typer.Option("all", "--scope")) -> None:
    project_root, cfg = _ctx()
    manager = MemoryManager(config=cfg, project_root=project_root)
    manager.purge(scope)
    typer.echo("ok")


@skill_app.command("list")
def skill_list() -> None:
    project_root, cfg = _ctx()
    dispatcher = AgentSkillDispatcher(config=cfg, project_root=project_root)
    for name in dispatcher.enabled_skills():
        typer.echo(name)


@skill_app.command("check")
def skill_check() -> None:
    project_root, cfg = _ctx()
    dispatcher = AgentSkillDispatcher(config=cfg, project_root=project_root)
    reports = dispatcher.health_check_detailed()
    for name, report in reports.items():
        typer.echo(f"{name}: {report.status}")
        for msg in report.issues:
            typer.echo(f"  - issue: {msg}")
        for msg in report.warnings:
            typer.echo(f"  - warn: {msg}")
        for msg in report.runtime:
            typer.echo(f"  - runtime: {msg}")


@workspace_app.command("show")
def workspace_show() -> None:
    project_root, cfg = _ctx()
    workspace_root = resolve_workspace_dir(cfg, project_root)
    typer.echo(str(workspace_root))


@workspace_app.command("set")
def workspace_set(path: str) -> None:
    project_root, _cfg = _ctx()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = (project_root / candidate).resolve()
    candidate.mkdir(parents=True, exist_ok=True)
    env_path = project_root / ".env"
    write_workspace_to_env(env_path, candidate)
    typer.echo(f"WORKSPACE_DIR={candidate}")
