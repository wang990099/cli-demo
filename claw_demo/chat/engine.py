from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from claw_demo.agent.workflow_runner import WorkflowAgentRunner
from claw_demo.chat.slash_commands import SlashResult, parse_slash
from claw_demo.config.schema import Config
from claw_demo.memory.manager import MemoryManager
from claw_demo.skills.dispatcher import AgentSkillDispatcher


HELP_TEXT = (
    "可用命令:\n"
    "/help - 查看帮助\n"
    "/exit - 退出聊天\n"
    "/reset - 清空短期会话\n"
    "/mem - 查看当前注入记忆\n"
    "/skills - 查看可用 skills\n"
    "/trace - 查看最近一次工作流轨迹\n"
    "/trace on|off - 开关自动显示轨迹\n"
    "/dryrun on|off - 开关邮件 dry-run\n"
    "/stream on|off - 开关流式输出"
)


class ChatEngine:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.history: list[dict[str, str]] = []
        self.last_memories: list[str] = []
        self.last_tool_trace: list[str] = []
        self.trace_auto_show = False
        self.memory = MemoryManager(config=config, project_root=project_root)
        self.dispatcher = AgentSkillDispatcher(config=config, project_root=project_root)
        self.workflow_runner = WorkflowAgentRunner(config=config, project_root=project_root)
        self._prompt_session = self._build_prompt_session()

    def _build_prompt_session(self):
        try:
            from prompt_toolkit import PromptSession

            return PromptSession()
        except Exception:
            return None

    def _read_user_input(self) -> str:
        if self._prompt_session is not None:
            try:
                return self._prompt_session.prompt("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                return "/exit"
        try:
            return input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            return "/exit"

    def run_loop(self) -> None:
        print("Claw CLI Demo. 输入 /help 查看命令帮助，/exit 退出")
        while True:
            user_input = self._read_user_input()
            if not user_input:
                continue
            slash = self._handle_slash(user_input)
            if slash.handled:
                if slash.output:
                    print(slash.output)
                if slash.should_exit:
                    break
                continue

            if self.config.chat.stream:
                print("bot> ", end="", flush=True)
                answer = self.handle_user_input(user_input, stream_writer=lambda chunk: print(chunk, end="", flush=True))
                print()
            else:
                answer = self.handle_user_input(user_input)
                print(f"bot> {answer}")

    def handle_user_input(
        self,
        user_input: str,
        stream_writer: Callable[[str], None] | None = None,
    ) -> str:
        memories = self.memory.search(user_input)
        self.last_memories = [f"{m.entry.key}: {m.snippet}" for m in memories]

        recent = self.history[-(self.config.chat.recent_turns * 2) :]

        result = self.workflow_runner.run(
            user_input=user_input,
            recent_messages=recent,
            memory_snippets=self.last_memories,
        )
        text = result.text
        self.last_tool_trace = result.tool_trace
        if self.trace_auto_show and self.last_tool_trace:
            text = text + "\n\n[trace]\n" + "\n".join(self.last_tool_trace)
        if stream_writer is not None:
            chunks = []
            chunk_size = 16
            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                chunks.append(chunk)
                stream_writer(chunk)
            text = "".join(chunks)

        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": text})
        self.memory.maybe_auto_extract(user_input, recent_messages=self.history[-8:])
        return text

    def _handle_slash(self, user_input: str) -> SlashResult:
        if not user_input.startswith("/"):
            return SlashResult(handled=False)
        cmd, arg = parse_slash(user_input)

        if cmd == "/exit":
            return SlashResult(handled=True, should_exit=True)
        if cmd == "/help":
            return SlashResult(handled=True, output=HELP_TEXT)
        if cmd == "/reset":
            self.history.clear()
            return SlashResult(handled=True, reset_history=True, output="短期会话已清空")
        if cmd == "/mem":
            text = "\n".join(self.last_memories) if self.last_memories else "当前无注入记忆"
            return SlashResult(handled=True, output=text)
        if cmd == "/skills":
            return SlashResult(handled=True, output=", ".join(self.dispatcher.enabled_skills()))
        if cmd == "/trace":
            if arg in {"on", "off"}:
                self.trace_auto_show = arg == "on"
                return SlashResult(handled=True, output=f"trace auto show = {self.trace_auto_show}")
            text = "\n".join(self.last_tool_trace) if self.last_tool_trace else "当前无工作流轨迹"
            return SlashResult(handled=True, output=text)
        if cmd == "/dryrun":
            if arg not in {"on", "off"}:
                return SlashResult(handled=True, output="用法: /dryrun on|off")
            self.config.email.dry_run = arg == "on"
            return SlashResult(handled=True, output=f"email dry-run = {self.config.email.dry_run}")
        if cmd == "/stream":
            if arg not in {"on", "off"}:
                return SlashResult(handled=True, output="用法: /stream on|off")
            self.config.chat.stream = arg == "on"
            return SlashResult(handled=True, output=f"chat stream = {self.config.chat.stream}")
        return SlashResult(handled=True, output=f"未知命令: {cmd}")
