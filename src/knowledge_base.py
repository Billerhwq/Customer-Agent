"""知识库加载：把 company / products / faq 扁平化为带 id 的文档列表。

每条文档保留原始 `id`，便于在输出的 sources 中引用证据。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .errors import AgentError, KNOWLEDGE_LOAD_FAILED


@dataclass
class KBDoc:
    id: str
    kind: str  # company | product | faq
    title: str
    text: str  # 用于检索与展示的合并文本
    raw: dict = field(default_factory=dict)

    def short_quote(self, max_len: int = 160) -> str:
        q = " ".join(self.text.split())
        return q if len(q) <= max_len else q[: max_len - 1] + "…"


class KnowledgeBase:
    def __init__(self, docs: list[KBDoc]):
        self.docs = docs
        self._by_id = {d.id: d for d in docs}

    def get(self, doc_id: str) -> KBDoc | None:
        return self._by_id.get(doc_id)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeBase":
        p = Path(path)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise AgentError(KNOWLEDGE_LOAD_FAILED, f"{KNOWLEDGE_LOAD_FAILED.message} ({exc})") from exc

        docs: list[KBDoc] = []

        company = data.get("company")
        if company:
            caps = ", ".join(company.get("capabilities", []))
            markets = ", ".join(company.get("markets", []))
            text = (
                f"{company.get('name', '')} — {company.get('business', '')}. "
                f"Location: {company.get('location', '')}. "
                f"Markets: {markets}. Capabilities: {caps}."
            )
            docs.append(
                KBDoc(
                    id=company.get("id", "C000"),
                    kind="company",
                    title=company.get("name", "Company"),
                    text=text,
                    raw=company,
                )
            )

        for prod in data.get("products", []):
            materials = ", ".join(prod.get("materials", []))
            text = (
                f"{prod.get('name', '')}. Materials: {materials}. "
                f"MOQ: {prod.get('moq', '')}. Lead time: {prod.get('lead_time', '')}. "
                f"Customization: {prod.get('customization', '')}."
            )
            docs.append(
                KBDoc(
                    id=prod["id"],
                    kind="product",
                    title=prod.get("name", prod["id"]),
                    text=text,
                    raw=prod,
                )
            )

        for faq in data.get("faq", []):
            text = f"Q: {faq.get('question', '')} A: {faq.get('answer', '')}"
            docs.append(
                KBDoc(
                    id=faq["id"],
                    kind="faq",
                    title=faq.get("question", faq["id"]),
                    text=text,
                    raw=faq,
                )
            )

        if not docs:
            raise AgentError(KNOWLEDGE_LOAD_FAILED, "Knowledge base is empty.")

        return cls(docs)
