from __future__ import annotations

from pathlib import Path

from claw_demo.chat.prompt_builder import build_messages
from claw_demo.chat.slash_commands import SlashResult, parse_slash
from claw_demo.config.schema import Config
from claw_demo.llm.client import LLMClient
from claw_demo.memory.manager import MemoryManager
from claw_demo.skills.dispatcher import SkillDispatcher


class ChatEngine:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.history: list[dict[str, str]] = []
        self.last_memories: list[str] = []
        self.memory = MemoryManager(config=config, project_root=project_root)
        self.dispatcher = SkillDispatcher(config=config, project_root=project_root)
        self.llm = LLMClient(config=config)

    def run_loop(self) -> None:
        print("Claw CLI Demo. 输入 /exit 退出")
        while True:
            user_input = input("you> ").strip()
            if not user_input:
                continue
            slash = self._handle_slash(user_input)
            if slash.handled:
                if slash.output:
                    print(slash.output)
                if slash.should_exit:
                    break
                continue

            answer = self.handle_user_input(user_input)
            print(f"bot> {answer}")

    def handle_user_input(self, user_input: str) -> str:
        memories = self.memory.search(user_input)
        self.last_memories = [f"{m.entry.key}: {m.snippet}" for m in memories]

        recent = self.history[-(self.config.chat.recent_turns * 2) :]
        messages = build_messages(
            "你是一个 CLI AI 助手。必要时使用技能。",
            recent=recent,
            user_text=user_input,
            memories=memories,
        )

        envelope = self.llm.plan_or_answer(
            messages=messages,
            memory_snippets=self.last_memories,
            skill_names=self.dispatcher.enabled_skills(),
        )

        if envelope.type == "skill_call" and envelope.skill is not None:
            skill_res = self.dispatcher.dispatch(envelope.skill.name, envelope.skill.args)
            text = self.llm.finalize_with_skill(user_text=user_input, skill_name=envelope.skill.name, skill_result_text=skill_res.text)
        else:
            text = envelope.text

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": text})
        self.memory.maybe_auto_extract(user_input)
        return text

    def _handle_slash(self, user_input: str) -> SlashResult:
        if not user_input.startswith("/"):
            return SlashResult(handled=False)
        cmd, arg = parse_slash(user_input)

        if cmd == "/exit":
            return SlashResult(handled=True, should_exit=True)
        if cmd == "/reset":
            self.history.clear()
            return SlashResult(handled=True, reset_history=True, output="短期会话已清空")
        if cmd == "/mem":
            text = "\n".join(self.last_memories) if self.last_memories else "当前无注入记忆"
            return SlashResult(handled=True, output=text)
        if cmd == "/skills":
            return SlashResult(handled=True, output=", ".join(self.dispatcher.enabled_skills()))
        if cmd == "/dryrun":
            if arg not in {"on", "off"}:
                return SlashResult(handled=True, output="用法: /dryrun on|off")
            self.config.email.dry_run = arg == "on"
            return SlashResult(handled=True, output=f"email dry-run = {self.config.email.dry_run}")
        return SlashResult(handled=True, output=f"未知命令: {cmd}")
