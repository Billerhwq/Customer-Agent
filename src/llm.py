"""LLM 层：统一接口 + mock 客户端 + DeepSeek 真实客户端。

- MockLLM：不调用外部 API，基于检索结果用规则拼出一段合理的 JSON 回答，
  保证无 key 也能跑通主流程。它会偶发地返回轻微不合法 JSON（带代码块围栏），
  用于演示 json_repair 的修复能力。
- DeepSeekLLM：调用 OpenAI 兼容的 /chat/completions 接口。
"""
from __future__ import annotations

import json
from typing import Protocol

import httpx

from .config import Settings
from .language import detect_language
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .retrieval import RetrievalHit


class LLMClient(Protocol):
    name: str

    def complete(self, message: str, hits: list[RetrievalHit],
                 visitor: dict | None, history: list[dict] | None) -> str:
        """返回 LLM 的原始文本输出（期望是 JSON 字符串）。"""
        ...


# --------------------------------------------------------------------------- #
# Mock
# --------------------------------------------------------------------------- #
class MockLLM:
    name = "mock"

    def complete(self, message, hits, visitor, history) -> str:
        visitor = visitor or {}
        lang = detect_language(message)
        has_kb = bool(hits) and hits[0].coverage >= 0.34

        sources = [{"id": h.doc.id, "quote": h.doc.short_quote(120)} for h in hits[:3]]

        if not message.strip():
            answer = "Could you tell me what product or service you are interested in?"
            need_human = False
            confidence = 0.2
            follow_ups = ["What product are you looking for?"]
            sources = []
        elif not has_kb:
            if lang == "zh":
                answer = ("这个问题目前不在我们的产品/资料范围内，我已记录您的需求，"
                          "我们的同事会尽快人工跟进。")
            else:
                answer = ("This is outside the information I currently have. I've logged your "
                          "request and a human colleague will follow up shortly.")
            need_human = True
            confidence = 0.3
            follow_ups = ["Could you share more detail about your requirement?"]
            sources = []
        else:
            top = hits[0].doc
            if lang == "zh":
                # 知识库为英文，mock 不翻译；中文回答保持纯中文，英文原文留在 sources 证据里
                answer = ("根据我们知识库中的相关资料，我们可以满足您的需求（具体依据见所引用的"
                          "知识库条目）。如需报价，请提供图纸、材料、数量、表面处理、公差和目的国。")
                follow_ups = ["能否提供图纸或 STEP 文件？", "需要的数量是多少？",
                              "有表面处理或公差要求吗？"]
            else:
                answer = (f"Based on our information: {top.short_quote(140)} "
                          "For a quotation, please share drawing, material, quantity, surface "
                          "treatment, tolerance, and destination country.")
                follow_ups = ["Could you share the drawing or STEP file?",
                              "What quantity do you need?",
                              "Any surface treatment or tolerance requirements?"]
            need_human = False
            confidence = round(min(0.95, 0.55 + hits[0].score * 0.4), 2)

        payload = {
            "answer": answer,
            "language": lang,
            "confidence": confidence,
            "sources": sources,
            "need_human": need_human,
            "lead_fields": {},  # 交由 agent 用规则抽取后合并
            "follow_up_questions": follow_ups,
        }
        text = json.dumps(payload, ensure_ascii=False)
        # 偶发：用代码块围栏包裹，演示 json_repair（基于消息长度的确定性触发）
        if len(message) % 7 == 3:
            text = f"```json\n{text}\n```"
        return text


# --------------------------------------------------------------------------- #
# DeepSeek (OpenAI 兼容)
# --------------------------------------------------------------------------- #
class DeepSeekLLM:
    name = "deepseek"

    def __init__(self, settings: Settings):
        self.settings = settings

    def complete(self, message, hits, visitor, history) -> str:
        s = self.settings
        url = f"{s.deepseek_base_url.rstrip('/')}/chat/completions"
        body = {
            "model": s.deepseek_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(message, hits, visitor, history)},
            ],
            "temperature": s.llm_temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {s.deepseek_api_key}",
                   "Content-Type": "application/json"}
        resp = httpx.post(url, json=body, headers=headers, timeout=s.llm_timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


def build_llm(settings: Settings) -> LLMClient:
    if settings.use_real_llm():
        return DeepSeekLLM(settings)
    return MockLLM()


_LANG_NAME = {"en": "English", "zh": "Simplified Chinese"}


def translate_text(settings: Settings, text: str, target: str) -> dict:
    """把文本翻译成目标语言（en/zh）。

    返回 {"text": 译文, "target": 目标语言, "mocked": 是否为 mock(未真正翻译)}。
    真实模式调用 DeepSeek；mock 模式无法真翻译，原样返回并标记 mocked=True。
    """
    target = target if target in _LANG_NAME else "en"
    if not text or not text.strip():
        return {"text": "", "target": target, "mocked": not settings.use_real_llm()}

    if not settings.use_real_llm():
        return {"text": text, "target": target, "mocked": True}

    s = settings
    url = f"{s.deepseek_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": s.deepseek_model,
        "messages": [
            {"role": "system",
             "content": (f"You are a professional translator. Translate the user's text "
                         f"into {_LANG_NAME[target]}. Preserve meaning, tone and any product "
                         f"specifics. Output ONLY the translation — no quotes, no notes, "
                         f"no explanations.")},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {s.deepseek_api_key}",
               "Content-Type": "application/json"}
    resp = httpx.post(url, json=body, headers=headers, timeout=s.llm_timeout)
    resp.raise_for_status()
    out = resp.json()["choices"][0]["message"]["content"].strip()
    return {"text": out, "target": target, "mocked": False}
