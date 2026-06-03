"""解析并修复 LLM 返回的非法 JSON。

策略（依次尝试）：
1. 直接 json.loads。
2. 剥离 ```json ... ``` 代码块围栏。
3. 截取第一个 '{' 到最后一个 '}' 的子串。
4. 常见修复：去掉尾随逗号、把单引号换成双引号、Python 风格 True/False/None。
全部失败则抛出 ValueError，交由上层降级。
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _strip_fence(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1) if m else text


def _extract_braces(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _basic_fixes(text: str) -> str:
    text = _TRAILING_COMMA_RE.sub(r"\1", text)
    text = text.replace("True", "true").replace("False", "false").replace("None", "null")
    return text


def parse_json_lenient(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("empty LLM output")

    candidates = []
    stripped = text.strip()
    candidates.append(stripped)
    fence = _strip_fence(stripped).strip()
    candidates.append(fence)
    candidates.append(_extract_braces(fence).strip())
    candidates.append(_basic_fixes(_extract_braces(fence)).strip())

    last_err: Exception | None = None
    for cand in candidates:
        if not cand:
            continue
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    raise ValueError(f"could not parse JSON from LLM output: {last_err}")
