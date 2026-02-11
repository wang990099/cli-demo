from __future__ import annotations

from claw_demo.config.loader import load_config
from claw_demo.memory.extractor import LLMMemoryExtractor, LLMMemoryVerifier
from claw_demo.memory.grep_retriever import MemoryEntry


def test_extractor_returns_empty_without_api_key() -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    extractor = LLMMemoryExtractor(cfg)
    rows = extractor.extract("我喜欢奶茶")
    assert rows == []


def test_parse_records_json_block() -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    extractor = LLMMemoryExtractor(cfg)
    raw = '{"records":[{"key":"pref:drink","mem_type":"profile","tags":["pref"],"content":"用户喜欢奶茶"}]}'
    parsed = extractor._parse_records(raw)
    assert parsed is not None
    assert parsed.records[0].key == "pref:drink"


def test_verifier_fallback_filters_noise_without_api_key() -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    verifier = LLMMemoryVerifier(cfg)
    rows = verifier.verify(
        user_text="测试",
        entries=[
            MemoryEntry("k1", "profile", ["a"], "2026-02-11", "好", None),
            MemoryEntry("k2", "profile", ["a"], "2026-02-11", "用户喜欢奶茶", None),
            MemoryEntry("k3", "profile", ["a"], "2026-02-11", "这个问题可以吗？", None),
            MemoryEntry("k2", "profile", ["a"], "2026-02-11", "用户喜欢奶茶", None),
        ],
    )
    assert len(rows) == 1
    assert rows[0].key == "k2"


def test_verifier_parse_decision_json_block() -> None:
    cfg = load_config()
    cfg.llm.api_key = ""
    verifier = LLMMemoryVerifier(cfg)
    parsed = verifier._parse_decision('{"keep":[0,2]}')
    assert parsed is not None
    assert parsed.keep == [0, 2]
