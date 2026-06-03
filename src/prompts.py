"""LLM 提示词构建。"""
from __future__ import annotations

from .language import detect_language
from .retrieval import RetrievalHit

SYSTEM_PROMPT = """You are a sales/customer-service assistant for a B2B foreign-trade
manufacturing company's website. Visitors ask about OEM/custom manufacturing, MOQ,
quotation requirements, materials, lead time, samples and shipping.

STRICT RULES:
1. Answer ONLY using the provided KNOWLEDGE snippets. Never invent specs, prices,
   MOQ, lead times or capabilities that are not in KNOWLEDGE.
2. If KNOWLEDGE does not contain the answer, set "need_human" to true and say a human
   colleague will follow up. Do NOT fabricate.
3. Prefer English for "answer" unless the visitor clearly writes in Chinese; then mirror
   their language. Set "language" to "en" or "zh" accordingly.
4. Every claim in "answer" must be backed by a source. Put the cited knowledge ids and a
   short verbatim quote in "sources".
5. Extract any sales lead fields the visitor mentioned into "lead_fields".
6. Ask the most useful next questions in "follow_up_questions".

OUTPUT: Return ONLY a single valid JSON object (no markdown, no prose) with EXACTLY these keys:
{
  "answer": string,
  "language": "en" | "zh",
  "confidence": number (0..1),
  "sources": [{"id": string, "quote": string}],
  "need_human": boolean,
  "lead_fields": {"product": string|null, "quantity": string|null, "country": string|null,
                  "email": string|null, "material": string|null, "drawing_available": boolean|null},
  "follow_up_questions": [string]
}
"""


def format_knowledge(hits: list[RetrievalHit]) -> str:
    if not hits:
        return "(no relevant knowledge found)"
    lines = []
    for h in hits:
        lines.append(f"[{h.doc.id}] ({h.doc.kind}, score={h.score}) {h.doc.text}")
    return "\n".join(lines)


def build_user_prompt(message: str, hits: list[RetrievalHit], visitor: dict | None,
                      history: list[dict] | None) -> str:
    visitor = visitor or {}
    parts = [f"KNOWLEDGE:\n{format_knowledge(hits)}", ""]
    if visitor:
        parts.append(f"VISITOR_CONTEXT: country={visitor.get('country') or 'unknown'}, "
                     f"email={visitor.get('email') or 'unknown'}")
    if history:
        convo = "\n".join(f"- {h.get('role', 'user')}: {h.get('content', '')}" for h in history[-6:])
        parts.append(f"CONVERSATION_SO_FAR:\n{convo}")
    parts.append(f"\nVISITOR_MESSAGE:\n{message}")

    # 硬性指定回答语言：访客用中文 -> 必须中文回答（镜像），否则英文（默认/优先英文）
    lang = detect_language(message)
    lang_name = "Chinese (简体中文)" if lang == "zh" else "English"
    parts.append(
        f"\nRESPONSE_LANGUAGE: The visitor's message is in {lang_name}. You MUST write the "
        f"\"answer\" field and \"follow_up_questions\" in {lang_name}, and set \"language\" "
        f"to \"{lang}\". Do not answer in any other language."
    )
    parts.append("\nReturn the JSON object now.")
    return "\n".join(parts)
