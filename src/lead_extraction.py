"""从访客消息中抽取询盘线索（规则版，作为 LLM 抽取的兜底与校正）。

字段：product / quantity / country / email / material / drawing_available
支持多轮累积：新值覆盖旧值，旧值在新消息未提及时保留。
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_QTY_RE = re.compile(r"(\d[\d,]*)\s*(?:pcs|pieces|units|个|件|套)?", re.IGNORECASE)

_MATERIALS = [
    "stainless steel", "carbon steel", "aluminum", "aluminium",
    "6061 aluminum", "7075 aluminum", "steel", "不锈钢", "碳钢", "铝",
]

_COUNTRIES = [
    "Germany", "Mexico", "United States", "USA", "US", "Canada", "France",
    "Italy", "Spain", "Netherlands", "UK", "United Kingdom", "Japan",
    "Korea", "Australia", "Brazil", "India", "德国", "墨西哥", "美国", "法国",
    "日本", "韩国", "英国",
]

_PRODUCT_HINTS = [
    "bracket", "stamping", "cnc", "aluminum part", "support frame", "frame",
    "welded", "machined", "支架", "冲压", "框架",
]

_DRAWING_HINTS = [
    "drawing", "step file", "step", "stp", "dxf", "pdf", "3d model", "图纸", "模型",
]


def _contains(text: str, term: str) -> bool:
    """ASCII 词用词边界匹配，避免 'US' 命中 'custom'；CJK 词用子串匹配。"""
    low = text.lower()
    t = term.lower()
    if re.search(r"[a-z]", t):
        # 允许可选复数 's'，使 'bracket' 命中 'brackets'
        return re.search(rf"(?<![a-z]){re.escape(t)}s?(?![a-z])", low) is not None
    return t in low


def _find_quantity(text: str) -> str | None:
    # 优先匹配带单位的数字
    m = re.search(r"(\d[\d,]*)\s*(?:pcs|pieces|units|个|件|套)", text, re.IGNORECASE)
    if m:
        return m.group(1).replace(",", "")
    # 退而求其次：句中较大的纯数字
    nums = [n.replace(",", "") for n in re.findall(r"\b(\d[\d,]{1,})\b", text)]
    nums = [n for n in nums if int(n) >= 10]  # 过滤掉年份/小数等噪音留给上层
    return nums[0] if nums else None


def _find_first(text: str, candidates: list[str]) -> str | None:
    for c in candidates:
        if _contains(text, c):
            return c
    return None


def extract_lead(message: str, visitor: dict | None = None) -> dict:
    text = message or ""
    visitor = visitor or {}

    email_match = _EMAIL_RE.search(text)
    email = email_match.group(0) if email_match else (visitor.get("email") or None)

    country = _find_first(text, _COUNTRIES) or (visitor.get("country") or None)
    material = _find_first(text, _MATERIALS)
    product = _find_first(text, _PRODUCT_HINTS)
    quantity = _find_quantity(text)

    drawing_available: bool | None = None
    if any(_contains(text, h) for h in _DRAWING_HINTS):
        drawing_available = True

    return {
        "product": product,
        "quantity": quantity,
        "country": country,
        "email": email or None,
        "material": material,
        "drawing_available": drawing_available,
    }


# 按"对报价的重要性"排序的字段 -> 缺失时该问的问题（中英双语）。
_FOLLOWUP_QUESTIONS: dict[str, dict[str, str]] = {
    "product": {
        "en": "Which product or part are you looking to source?",
        "zh": "您想采购哪款产品或零件？",
    },
    "drawing_available": {
        "en": "Do you have a drawing, sample or 3D model we can quote from?",
        "zh": "您是否有可用于报价的图纸、样品或 3D 模型？",
    },
    "quantity": {
        "en": "What quantity (pcs) do you need?",
        "zh": "您需要的数量是多少（件）？",
    },
    "material": {
        "en": "Which material should we use (e.g. aluminum, carbon steel)?",
        "zh": "需要使用什么材料（如铝、碳钢）？",
    },
    "country": {
        "en": "Which destination country should we ship to?",
        "zh": "货物的目的国是哪里？",
    },
    "email": {
        "en": "What's the best email to send the formal quotation to?",
        "zh": "正式报价单发送到哪个邮箱比较好？",
    },
}

_ALL_FILLED = {
    "en": "Great, I have all the key details — shall I prepare a formal quotation now?",
    "zh": "关键信息已齐全，需要我据此整理一份正式报价单吗？",
}


def followups_from_lead(lead: dict | None, lang: str, limit: int = 3) -> list[str]:
    """根据累积线索里仍缺失的字段，精准生成"下一步该问的问题"。

    字段按对报价的重要性排序，最多返回 `limit` 条；全部齐全时转为确认报价。
    """
    lang = "zh" if lang == "zh" else "en"
    lead = lead or {}
    missing = [
        field for field in _FOLLOWUP_QUESTIONS
        if lead.get(field) in (None, "")
    ]
    if not missing:
        return [_ALL_FILLED[lang]]
    return [_FOLLOWUP_QUESTIONS[f][lang] for f in missing[:limit]]


def merge_leads(old: dict | None, new: dict | None) -> dict:
    """多轮累积：new 中的非空值覆盖 old，其余保留 old。"""
    base = {
        "product": None, "quantity": None, "country": None,
        "email": None, "material": None, "drawing_available": None,
    }
    base.update({k: v for k, v in (old or {}).items() if v is not None})
    for k, v in (new or {}).items():
        if v is not None:
            base[k] = v
    return base
