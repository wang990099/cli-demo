from __future__ import annotations

from claw_demo.memory.grep_retriever import RetrievedMemory


def build_messages(system_prompt: str, recent: list[dict[str, str]], user_text: str, memories: list[RetrievedMemory]) -> list[dict[str, str]]:
    memory_block = "\n".join(f"- {m.entry.key}: {m.snippet}" for m in memories)
    mem_prefix = f"Long-term Memory:\n{memory_block}\n\n" if memory_block else ""
    return [{"role": "system", "content": system_prompt + "\n" + mem_prefix}] + recent + [{"role": "user", "content": user_text}]
