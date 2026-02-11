from __future__ import annotations

from datetime import date
from pathlib import Path

from claw_demo.memory.grep_retriever import MemoryEntry
from claw_demo.memory.normalize import normalize_tags, normalize_updated_at


def _target_file(memory_root: Path, mem_type: str) -> Path:
    if mem_type == "profile":
        return memory_root / "profile.md"
    if mem_type == "episode":
        return memory_root / "episodes" / f"{date.today().isoformat()}-episode.md"
    return memory_root / "facts.md"


def _parse_blocks(text: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    chunks = [c for c in text.split("\n## ") if c.strip()]
    for idx, chunk in enumerate(chunks):
        block = chunk if idx == 0 and chunk.startswith("## ") else "## " + chunk
        lines = block.splitlines()
        if not lines:
            continue
        key = lines[0].replace("## ", "", 1).strip()
        blocks[key] = block.rstrip() + "\n"
    return blocks


def _render_entry(entry: MemoryEntry) -> str:
    tags = ",".join(normalize_tags(entry.tags))
    updated_at = normalize_updated_at(entry.updated_at)
    return (
        f"## {entry.key}\n"
        f"- type: {entry.mem_type}\n"
        f"- tags: {tags}\n"
        f"- updated_at: {updated_at}\n"
        f"- content: {entry.content}\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def rebuild_index(memory_root: Path) -> None:
    index_path = memory_root / "index" / "memory_keys.tsv"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, str] = {}
    files = [memory_root / "profile.md", memory_root / "facts.md"]
    files.extend(sorted((memory_root / "episodes").glob("*.md")))
    for file in files:
        if not file.exists():
            continue
        text = file.read_text(encoding="utf-8")
        for line in text.splitlines():
            if not line.startswith("## "):
                continue
            key = line.replace("## ", "", 1).strip()
            if key:
                rows[key] = file.name
    body = "\n".join(f"{k}\t{v}" for k, v in sorted(rows.items())) + "\n"
    _atomic_write(index_path, body)


def upsert_entry(memory_root: Path, entry: MemoryEntry) -> None:
    target = _target_file(memory_root, entry.mem_type)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    blocks = _parse_blocks(existing)
    if entry.key in blocks:
        del blocks[entry.key]
    blocks[entry.key] = _render_entry(entry)
    content = "\n".join(block.strip() for block in blocks.values()) + "\n"
    _atomic_write(target, content)
    rebuild_index(memory_root)


def replace_entries(memory_root: Path, mem_type: str, entries: list[MemoryEntry]) -> None:
    if mem_type == "profile":
        target = memory_root / "profile.md"
    elif mem_type == "fact":
        target = memory_root / "facts.md"
    else:
        raise ValueError("replace_entries only supports profile|fact")

    blocks: dict[str, str] = {}
    for entry in entries:
        blocks[entry.key] = _render_entry(entry)
    content = "\n".join(block.strip() for block in blocks.values()) + "\n" if blocks else ""
    _atomic_write(target, content)
    rebuild_index(memory_root)


def purge_memory(memory_root: Path, scope: str) -> None:
    if scope in {"profile", "all"}:
        _atomic_write(memory_root / "profile.md", "")
    if scope in {"fact", "all"}:
        _atomic_write(memory_root / "facts.md", "")
    if scope in {"episode", "all"}:
        for p in (memory_root / "episodes").glob("*.md"):
            p.unlink(missing_ok=True)
    rebuild_index(memory_root)
