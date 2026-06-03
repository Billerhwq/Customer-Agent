"""极简语言检测：区分中文 / 英文。"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[一-鿿]")


def detect_language(text: str) -> str:
    if not text:
        return "en"
    cjk = len(_CJK_RE.findall(text))
    # 只要有一定比例中文字符即判为中文
    if cjk >= 2 or (cjk >= 1 and cjk / max(len(text), 1) > 0.1):
        return "zh"
    return "en"
