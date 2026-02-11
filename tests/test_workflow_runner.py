from __future__ import annotations

from pathlib import Path

from claw_demo.agent.workflow_runner import WorkflowAgentRunner
from claw_demo.config.loader import load_config


def test_workflow_requires_llm(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    cfg.file_access.workspace_dir = str(tmp_path)
    runner = WorkflowAgentRunner(config=cfg, project_root=tmp_path)
    result = runner.run("搜索到app.log文件，将文件总结，发送给wang990099@163.com")
    assert not result.ok
    assert "LLM 不可用" in result.text


def test_required_tools_for_compound_request(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    cfg.file_access.workspace_dir = str(tmp_path)
    runner = WorkflowAgentRunner(config=cfg, project_root=tmp_path)
    tools = runner._required_tools("搜索到app.log文件，将文件总结，发送给wang990099@163.com")
    assert tools == ["file_search", "file_read", "summarize", "email"]


def test_required_tools_for_time_request(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    cfg.file_access.workspace_dir = str(tmp_path)
    runner = WorkflowAgentRunner(config=cfg, project_root=tmp_path)
    tools = runner._required_tools("现在几点了")
    assert tools == ["time"]
