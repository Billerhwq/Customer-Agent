"""单元测试（pytest）。覆盖 README §5 的 6 种必须处理情况 + 加分项。

运行： python -m pytest -q
默认 mock 模式，无需任何 API key。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("LLM_MODE", "mock")
# 用独立的临时数据库，避免测试间/与开发库相互污染
import tempfile  # noqa: E402

_TEST_DB = Path(tempfile.gettempdir()) / "fts_agent_test.db"
if _TEST_DB.exists():
    _TEST_DB.unlink()
os.environ["DB_PATH"] = str(_TEST_DB)

from src.agent import Agent  # noqa: E402
from src.errors import AgentError, EMPTY_INPUT  # noqa: E402
from src.json_repair import parse_json_lenient  # noqa: E402
from src.lead_extraction import (  # noqa: E402
    extract_lead,
    followups_from_lead,
    merge_leads,
)

SCHEMA = json.loads((ROOT / "schema" / "output_schema.json").read_text(encoding="utf-8"))


@pytest.fixture()
def agent():
    return Agent()


def _assert_schema(result: dict):
    for key in SCHEMA["required"]:
        assert key in result, f"missing key: {key}"
    assert 0.0 <= result["confidence"] <= 1.0
    assert isinstance(result["sources"], list)
    assert isinstance(result["need_human"], bool)
    assert isinstance(result["follow_up_questions"], list)


def test_case_known_answer(agent):
    """情况 1：知识库有明确答案 -> 引用证据。"""
    r = agent.chat("Can you make custom stainless steel brackets based on my drawing?",
                   session_id="t1")
    _assert_schema(r)
    assert r["need_human"] is False
    assert any(s["id"] in {"P001", "F002", "F003", "C001"} for s in r["sources"])


def test_case_moq(agent):
    """情况 1：MOQ 查询命中 P002。"""
    r = agent.chat("What is the MOQ for CNC aluminum parts?", session_id="t2")
    _assert_schema(r)
    assert any(s["id"] == "P002" for s in r["sources"])


def test_case_out_of_scope(agent):
    """情况 2：知识库无相关信息 -> need_human=true，不编造。"""
    r = agent.chat("Do you sell plastic toys?", session_id="t3")
    _assert_schema(r)
    assert r["need_human"] is True


def test_case_empty_input(agent):
    """情况 6：空输入 -> 明确错误，不崩溃。"""
    with pytest.raises(AgentError) as ei:
        agent.chat("   ", session_id="t4")
    assert ei.value.error.code == EMPTY_INPUT.code


def test_case_lead_extraction(agent):
    """情况 4：抽取询盘线索。"""
    r = agent.chat(
        "I need 2000 carbon steel brackets, powder coated, shipped to Mexico. "
        "What do you need for quotation?",
        session_id="t5",
    )
    _assert_schema(r)
    lead = r["lead_fields"]
    assert lead["quantity"] == "2000"
    assert lead["material"] == "carbon steel"
    assert lead["country"] == "Mexico"


def test_multi_turn_accumulation(agent):
    """加分项：多轮线索累积。"""
    agent.chat("I need carbon steel brackets.", session_id="multi")
    agent.chat("Quantity is 2000 pcs.", session_id="multi")
    r = agent.chat("Ship to Mexico, my email is buyer@acme.com", session_id="multi")
    lead = r["lead_fields"]
    assert lead["material"] == "carbon steel"
    assert lead["quantity"] == "2000"
    assert lead["country"] == "Mexico"
    assert lead["email"] == "buyer@acme.com"


def test_chinese_question(agent):
    """加分项：中文问题 -> 中文回答，且经术语桥接命中英文知识库。"""
    r = agent.chat("你们不锈钢支架的最小起订量是多少？", session_id="zh")
    _assert_schema(r)
    assert r["language"] == "zh"
    assert r["need_human"] is False
    assert any(s["id"] in {"P001", "P002", "P003"} for s in r["sources"])


def test_chinese_out_of_scope(agent):
    """中文越界问题（塑料玩具）-> need_human=true，不编造。"""
    r = agent.chat("你们卖塑料玩具吗？", session_id="zh-oos")
    _assert_schema(r)
    assert r["need_human"] is True


def test_json_repair_fenced():
    """情况 5：非法 JSON（代码块围栏 + 尾随逗号）可被修复。"""
    bad = "```json\n{\"answer\": \"hi\", \"need_human\": false,}\n```"
    obj = parse_json_lenient(bad)
    assert obj["answer"] == "hi"


def test_json_repair_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_json_lenient("totally not json")


def test_lead_merge_keeps_old():
    old = {"material": "aluminum", "country": "Germany"}
    new = {"country": "Mexico", "quantity": "100"}
    merged = merge_leads(old, new)
    assert merged["material"] == "aluminum"  # 旧值保留
    assert merged["country"] == "Mexico"     # 新值覆盖
    assert merged["quantity"] == "100"


def test_followups_target_missing_fields():
    """增强：追问只针对仍缺失的线索字段，按重要性排序，最多 3 条。"""
    lead = {"product": "bracket", "quantity": None, "country": None,
            "email": None, "material": "carbon steel", "drawing_available": None}
    qs = followups_from_lead(lead, "en")
    assert len(qs) == 3
    text = " ".join(qs).lower()
    assert "quantity" in text and "country" in text and ("drawing" in text or "model" in text)
    # 已填字段不再追问
    assert "material" not in text and "which product" not in text


def test_followups_all_filled_asks_quote():
    full = {"product": "bracket", "quantity": "2000", "country": "Mexico",
            "email": "a@b.com", "material": "carbon steel", "drawing_available": True}
    assert followups_from_lead(full, "en") == [
        "Great, I have all the key details — shall I prepare a formal quotation now?"
    ]
    zh = followups_from_lead(full, "zh")
    assert "报价单" in zh[0]


def test_followups_in_chat_are_gap_driven(agent):
    """端到端：可回答场景下，回答的 follow-ups 来自缺口字段而非泛化模板。"""
    r = agent.chat("What is the MOQ for CNC aluminum parts?", session_id="fu")
    _assert_schema(r)
    assert r["need_human"] is False
    joined = " ".join(r["follow_up_questions"]).lower()
    assert "quantity" in joined or "country" in joined or "drawing" in joined
