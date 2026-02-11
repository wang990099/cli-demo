from __future__ import annotations

from pathlib import Path

from claw_demo.chat.engine import ChatEngine
from claw_demo.config.loader import load_config
from claw_demo.memory.grep_retriever import MemoryEntry


class StubExtractor:
    def __init__(self, mapping: dict[str, list[MemoryEntry]]) -> None:
        self.mapping = mapping

    def extract(self, user_text: str, recent_messages=None) -> list[MemoryEntry]:
        return self.mapping.get(user_text, [])


class StubWorkflowResult:
    def __init__(self, text: str, tool_trace: list[str] | None = None) -> None:
        self.ok = True
        self.text = text
        self.tool_trace: list[str] = tool_trace or []


def _entry(key: str, mem_type: str, content: str, tags: list[str] | None = None) -> MemoryEntry:
    return MemoryEntry(
        key=key,
        mem_type=mem_type,
        tags=tags or [mem_type],
        updated_at="2026-02-11",
        content=content,
        source_file=None,
    )


def test_chat_skill_roundtrip(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.workflow_runner.run = lambda **kwargs: StubWorkflowResult("hello")  # type: ignore[assignment]
    out = engine.handle_user_input("请读文件 README.md")
    assert "hello" in out


def test_auto_memory_extract_with_injected_llm_extractor(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.memory.extractor = StubExtractor(
        {
            "我喜欢奶茶": [_entry("pref:drink", "profile", "用户喜欢奶茶", ["pref", "drink"])],
            "我还喜欢游泳": [_entry("pref:hobby", "profile", "用户喜欢游泳", ["pref", "hobby"])],
        }
    )

    engine.handle_user_input("我喜欢奶茶")
    engine.handle_user_input("我还喜欢游泳")
    rows = engine.memory.search("喜欢")
    assert rows
    text = "\n".join(item.entry.content for item in rows)
    assert "奶茶" in text
    assert "游泳" in text


def test_reset_does_not_drop_long_term_memory(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.memory.extractor = StubExtractor(
        {
            "记住我喜欢奶茶": [_entry("pref:drink", "profile", "用户喜欢奶茶", ["pref"])],
        }
    )
    engine.handle_user_input("记住我喜欢奶茶")
    res = engine._handle_slash("/reset")
    assert res.handled

    rows = engine.memory.search("喜欢")
    assert rows
    assert "奶茶" in rows[0].entry.content


def test_chat_stream_writer(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    cfg.chat.stream = True
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.workflow_runner.run = lambda **kwargs: StubWorkflowResult("hello")  # type: ignore[assignment]
    chunks: list[str] = []
    final = engine.handle_user_input(
        "请读文件 README.md",
        stream_writer=lambda chunk: chunks.append(chunk),
    )
    assert chunks
    assert "".join(chunks) == final
    assert "hello" in final


def test_stream_slash_toggle(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    cfg.chat.stream = True

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    off = engine._handle_slash("/stream off")
    assert off.handled
    assert engine.config.chat.stream is False
    on = engine._handle_slash("/stream on")
    assert on.handled
    assert engine.config.chat.stream is True


def test_help_slash_command(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    res = engine._handle_slash("/help")
    assert res.handled
    assert "/exit" in res.output
    assert "/stream on|off" in res.output
    assert "/command help <命令>" in res.output


def test_trace_commands_and_auto_show(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.workflow_runner.run = lambda **kwargs: StubWorkflowResult("done", ["file_search ...", "file_read ..."])  # type: ignore[assignment]

    toggle = engine._handle_slash("/trace on")
    assert toggle.handled
    assert "True" in toggle.output

    out = engine.handle_user_input("测试任务")
    assert "[trace]" in out
    assert "file_search" in out

    show = engine._handle_slash("/trace")
    assert show.handled
    assert "file_read" in show.output

    off = engine._handle_slash("/trace off")
    assert off.handled
    assert "False" in off.output


def test_command_help_and_mem_help(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    cmd_help = engine._handle_slash("/command help /mem")
    assert cmd_help.handled
    assert "/mem help" in cmd_help.output

    mem_help = engine._handle_slash("/mem help")
    assert mem_help.handled
    assert "当前这轮检索注入" in mem_help.output


def test_memtype_toggle_and_apply(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.memory.root = "./memory"
    cfg.file_access.workspace_dir = str(tmp_path)
    cfg.llm.api_key = ""
    cfg.memory.default_mem_type = "auto"

    engine = ChatEngine(config=cfg, project_root=tmp_path)
    engine.workflow_runner.run = lambda **kwargs: StubWorkflowResult("done", [])  # type: ignore[assignment]

    show = engine._handle_slash("/memtype")
    assert show.handled
    assert "auto" in show.output

    set_profile = engine._handle_slash("/memtype profile")
    assert set_profile.handled
    assert "profile" in set_profile.output

    captured: dict[str, str | None] = {}

    def _capture(user_text, recent_messages=None, mem_type_override=None):
        captured["value"] = mem_type_override

    engine.memory.maybe_auto_extract = _capture  # type: ignore[assignment]
    engine.handle_user_input("测试写入")
    assert captured["value"] == "profile"
