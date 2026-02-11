from __future__ import annotations

from datetime import date
from pathlib import Path

from claw_demo.memory.grep_retriever import MemoryEntry


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
    tags = ",".join(entry.tags)
    return (
        f"## {entry.key}\n"
        f"- type: {entry.mem_type}\n"
        f"- tags: {tags}\n"
        f"- updated_at: {entry.updated_at}\n"
        f"- content: {entry.content}\n"
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def _update_index(memory_root: Path, key: str, file_name: str) -> None:
    index_path = memory_root / "index" / "memory_keys.tsv"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, str] = {}
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            k, v = line.split("\t", 1)
            rows[k.strip()] = v.strip()
    rows[key] = file_name
    body = "\n".join(f"{k}\t{v}" for k, v in sorted(rows.items())) + "\n"
    _atomic_write(index_path, body)


def _remove_index_key(memory_root: Path, key: str) -> None:
    index_path = memory_root / "index" / "memory_keys.tsv"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    rows: dict[str, str] = {}
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or "\t" not in line:
                continue
            k, v = line.split("\t", 1)
            rows[k.strip()] = v.strip()
    rows.pop(key, None)
    body = "\n".join(f"{k}\t{v}" for k, v in sorted(rows.items()))
    if body:
        body += "\n"
    _atomic_write(index_path, body)


def upsert_entry(memory_root: Path, entry: MemoryEntry) -> None:
    target = _target_file(memory_root, entry.mem_type)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    blocks = _parse_blocks(existing)
    blocks[entry.key] = _render_entry(entry)
    content = "\n".join(block.strip() for _, block in sorted(blocks.items())) + "\n"
    _atomic_write(target, content)
    _update_index(memory_root, entry.key, target.name)


def delete_entry(memory_root: Path, key: str, mem_type: str = "profile") -> None:
    target = _target_file(memory_root, mem_type)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    blocks = _parse_blocks(existing)
    if key in blocks:
        del blocks[key]
        body = "\n".join(block.strip() for _, block in sorted(blocks.items()))
        if body:
            body += "\n"
        _atomic_write(target, body)
    _remove_index_key(memory_root, key)


def purge_memory(memory_root: Path, scope: str) -> None:
    if scope in {"profile", "all"}:
        _atomic_write(memory_root / "profile.md", "")
    if scope in {"fact", "all"}:
        _atomic_write(memory_root / "facts.md", "")
    if scope in {"episode", "all"}:
        for p in (memory_root / "episodes").glob("*.md"):
            p.unlink(missing_ok=True)
    if scope == "all":
        _atomic_write(memory_root / "index" / "memory_keys.tsv", "")
