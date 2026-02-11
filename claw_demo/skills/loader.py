from __future__ import annotations

from pathlib import Path

from claw_demo.skills.models import AgentSkillSpec


class SkillLoader:
    def __init__(self, builtin_root: Path, import_roots: list[Path] | None = None) -> None:
        self.builtin_root = builtin_root
        self.import_roots = import_roots or []

    def load(self, name: str) -> AgentSkillSpec | None:
        for spec in self.list_skills():
            if spec.name == name:
                return spec
        return None

    def list_skills(self) -> list[AgentSkillSpec]:
        # Merge order: builtin first, then external imports override by name.
        merged: dict[str, AgentSkillSpec] = {}
        for root in [self.builtin_root, *self.import_roots]:
            for spec in self._scan_root(root):
                merged[spec.name] = spec
        return [merged[k] for k in sorted(merged.keys())]

    def _scan_root(self, root: Path) -> list[AgentSkillSpec]:
        if not root.exists():
            return []
        base = root / "agents" if (root / "agents").exists() else root
        items: list[AgentSkillSpec] = []
        for p in sorted(base.iterdir()):
            if not p.is_dir():
                continue
            skill_file = p / "SKILL.md"
            if not skill_file.exists():
                continue
            content = skill_file.read_text(encoding="utf-8")
            items.append(self._parse(p.name, skill_file, content))
        return items

    def _parse(self, fallback_name: str, skill_file: Path, content: str) -> AgentSkillSpec:
        lines = content.splitlines()
        meta: dict[str, str] = {}
        body_lines: list[str] = []
        in_meta = True
        for line in lines:
            if in_meta and ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
            else:
                in_meta = False
                body_lines.append(line)

        name = meta.get("name", fallback_name)
        description = meta.get("description", "")
        instructions = "\n".join(body_lines).strip()
        if not instructions:
            instructions = description or f"Use skill {name} to solve the request."
        return AgentSkillSpec(
            name=name,
            description=description,
            instructions=instructions,
            directory_name=fallback_name,
            source_path=skill_file,
        )
