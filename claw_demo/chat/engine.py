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
    "/mem [help] - 查看当前注入记忆或使用说明\n"
    "/memtype [auto|profile|fact|episode] - 查看或切换会话记忆类型\n"
    "/skills - 查看可用 skills\n"
    "/command help <命令> - 查看某个命令详细使用\n"
    "/trace - 查看最近一次工作流轨迹\n"
    "/trace on|off - 开关自动显示轨迹\n"
    "/dryrun on|off - 开关邮件 dry-run\n"
    "/stream on|off - 开关流式输出"
)

COMMAND_HELP: dict[str, str] = {
    "/help": "用法: /help\n说明: 显示所有可用命令概览。",
    "/exit": "用法: /exit\n说明: 退出 chat 会话。",
    "/reset": "用法: /reset\n说明: 只清空短期会话历史，不会删除长期记忆。",
    "/mem": (
        "用法:\n"
        "/mem\n"
        "/mem help\n"
        "说明:\n"
        "- `/mem` 显示当前这轮检索注入到 prompt 的记忆片段。\n"
        "- `/mem help` 查看本命令说明。\n"
        "注意:\n"
        "- 若显示“当前无注入记忆”，表示本轮查询未命中长期记忆。\n"
        "- 可尝试换关键词后再问，或用 `claw mem search \"关键词\"` 手动排查。"
    ),
    "/memtype": (
        "用法:\n"
        "/memtype\n"
        "/memtype auto|profile|fact|episode\n"
        "说明:\n"
        "- `/memtype` 查看当前会话记忆类型。\n"
        "- `/memtype profile|fact|episode` 强制本会话新写入记忆类型。\n"
        "- `/memtype auto` 恢复由模型自行决定记忆类型。"
    ),
    "/skills": "用法: /skills\n说明: 显示当前启用的 Agent Skills 列表。",
    "/trace": (
        "用法:\n"
        "/trace\n"
        "/trace on\n"
        "/trace off\n"
        "说明:\n"
        "- `/trace` 查看最近一次工作流工具调用轨迹。\n"
        "- `/trace on|off` 开关每次回答后自动附带轨迹。"
    ),
    "/dryrun": "用法: /dryrun on|off\n说明: 控制 email 工具是否仅预演发送（默认 on）。",
    "/stream": "用法: /stream on|off\n说明: 控制回答是否以流式方式输出。",
    "/command": (
        "用法:\n"
        "/command help <命令>\n"
        "示例:\n"
        "/command help /mem\n"
        "/command help mem\n"
        "说明:\n"
        "- 查看某一个命令的详细使用说明。"
    ),
}


class ChatEngine:
    def __init__(self, config: Config, project_root: Path) -> None:
        self.config = config
        self.project_root = project_root
        self.history: list[dict[str, str]] = []
        self.last_memories: list[str] = []
        self.current_mem_type = config.memory.default_mem_type
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
        self.memory.maybe_auto_extract(
            user_input,
            recent_messages=self.history[-8:],
            mem_type_override=self.current_mem_type,
        )
        return text

    def _handle_slash(self, user_input: str) -> SlashResult:
        if not user_input.startswith("/"):
            return SlashResult(handled=False)
        cmd, arg = parse_slash(user_input)

        if cmd == "/exit":
            return SlashResult(handled=True, should_exit=True)
        if cmd == "/help":
            return SlashResult(handled=True, output=HELP_TEXT)
        if cmd == "/command":
            if not arg:
                return SlashResult(handled=True, output=COMMAND_HELP["/command"])
            parts = arg.strip().split(maxsplit=1)
            if parts[0].lower() != "help":
                return SlashResult(handled=True, output="用法: /command help <命令>")
            if len(parts) == 1 or not parts[1].strip():
                available = ", ".join(sorted(COMMAND_HELP.keys()))
                return SlashResult(handled=True, output=f"请指定命令。可选: {available}")
            target = parts[1].strip()
            if not target.startswith("/"):
                target = "/" + target
            detail = COMMAND_HELP.get(target)
            if detail is None:
                return SlashResult(handled=True, output=f"未知命令: {target}")
            return SlashResult(handled=True, output=detail)
        if cmd == "/reset":
            self.history.clear()
            return SlashResult(handled=True, reset_history=True, output="短期会话已清空")
        if cmd == "/mem":
            if arg and arg.strip().lower() in {"help", "-h", "--help"}:
                return SlashResult(handled=True, output=COMMAND_HELP["/mem"])
            if self.last_memories:
                text = "当前注入记忆:\n" + "\n".join(f"- {m}" for m in self.last_memories)
            else:
                text = (
                    "当前无注入记忆。\n"
                    "可用 `/mem help` 查看说明，或使用 `/command help /mem` 查看详细用法。"
                )
            return SlashResult(handled=True, output=text)
        if cmd == "/memtype":
            if not arg:
                return SlashResult(handled=True, output=f"current memtype = {self.current_mem_type}")
            target = arg.strip().lower()
            allowed = {"auto", "profile", "fact", "episode"}
            if target not in allowed:
                return SlashResult(handled=True, output="用法: /memtype auto|profile|fact|episode")
            self.current_mem_type = target
            return SlashResult(handled=True, output=f"current memtype = {self.current_mem_type}")
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
