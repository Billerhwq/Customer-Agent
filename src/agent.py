"""Agent 编排核心：检索 -> LLM -> JSON 解析/修复/重试/降级 -> 校验 -> 输出。

处理 README §5 要求的 6 种情况，支持多轮线索累积；会话状态持久化到 SQLite，
重启后「最近会话 / 历史 / 线索」依然可用。
"""
from __future__ import annotations

import time
import uuid

from .config import Settings, get_settings
from .errors import AgentError, EMPTY_INPUT, LLM_CALL_FAILED, LLM_INVALID_JSON
from .json_repair import parse_json_lenient
from .knowledge_base import KnowledgeBase
from .language import detect_language
from .lead_extraction import extract_lead, followups_from_lead, merge_leads
from .llm import build_llm
from .logging_utils import TraceLogger
from .retrieval import BM25Retriever, RetrievalHit
from .store import SessionStore

_REQUIRED_KEYS = ["answer", "language", "confidence", "sources", "need_human",
                  "lead_fields", "follow_up_questions", "trace_id"]


class Agent:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.kb = KnowledgeBase.load(self.settings.knowledge_path)
        self.retriever = BM25Retriever(self.kb)
        self.llm = build_llm(self.settings)
        self.logger = TraceLogger(self.settings.log_path)
        self.store = SessionStore(self.settings.db_path)

    # ----------------------------- public ------------------------------ #
    def chat(self, message: str, session_id: str | None = None,
             visitor: dict | None = None) -> dict:
        trace_id = str(uuid.uuid4())
        visitor = visitor or {}
        sid = session_id or trace_id
        t0 = time.perf_counter()

        # 情况 6：输入为空 -> 明确错误，不崩溃
        if not message or not message.strip():
            err = AgentError(EMPTY_INPUT)
            self.logger.log({"trace_id": trace_id, "input": message,
                             "error": err.detail, "error_code": err.error.code,
                             "degraded": False})
            raise err

        # 会话持久化：确保会话存在、取历史与已累积线索
        self.store.ensure_session(sid, visitor, message)
        history = self.store.get_history(sid)
        prior_lead = self.store.get_lead(sid)

        # 1) 检索（用实义词覆盖率判断知识库是否真的相关）
        hits = self.retriever.search(message, top_k=self.settings.retrieval_top_k)
        has_kb = bool(hits) and hits[0].coverage >= self.settings.retrieval_min_score

        # 2) 调 LLM（带重试 + 修复 + 降级）
        raw_output = None
        parsed = None
        degraded = False
        error_code = None
        attempts = 0
        last_err = None

        for attempts in range(1, self.settings.llm_max_retries + 2):
            try:
                raw_output = self.llm.complete(message, hits, visitor, history)
            except Exception as exc:  # noqa: BLE001 LLM 网络/服务异常
                last_err = exc
                raw_output = None
                continue
            try:
                parsed = parse_json_lenient(raw_output)
                break
            except Exception as exc:  # noqa: BLE001 非法 JSON
                last_err = exc
                error_code = LLM_INVALID_JSON.code
                parsed = None
                continue

        # 3) 降级：LLM 全部失败 -> 规则兜底
        if parsed is None:
            degraded = True
            error_code = (LLM_CALL_FAILED.code if raw_output is None
                          else LLM_INVALID_JSON.code)
            parsed = self._fallback_answer(message, hits, has_kb)

        # 4) 规范化 + 校验 + 线索合并
        result = self._normalize(parsed, message, hits, has_kb, visitor,
                                 prior_lead, trace_id)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # UI 遥测（非 schema 必需字段，规范的 8 个字段不受影响）
        result["meta"] = {
            "latency_ms": latency_ms,
            "llm_mode": self.llm.name,
            "degraded": degraded,
            "error_code": error_code,
            "kb_total": len(self.kb.docs),
            "retrieved": [{"id": h.doc.id, "score": h.score, "coverage": h.coverage}
                          for h in hits],
            "attempts": attempts,
        }

        # 5) 持久化：线索 + 两条消息（agent 消息带完整 meta，供历史/分析/追踪复原）
        self.store.update_lead(sid, result["lead_fields"])
        self.store.append_message(sid, "visitor", message)
        self.store.append_message(sid, "agent", result["answer"], meta={
            "trace_id": trace_id,
            "language": result["language"],
            "confidence": result["confidence"],
            "sources": result["sources"],
            "need_human": result["need_human"],
            "follow_up_questions": result["follow_up_questions"],
            "lead_fields": result["lead_fields"],
            **result["meta"],
            "llm_raw_output": raw_output,
        })

        # 6) 写追踪日志（README §6 要求字段）
        self.logger.log({
            "trace_id": trace_id,
            "session_id": sid,
            "input": message,
            "visitor": visitor,
            "retrieved": result["meta"]["retrieved"],
            "llm_mode": self.llm.name,
            "llm_raw_output": raw_output,
            "final_output": result,
            "error_code": error_code,
            "degraded": degraded,
            "attempts": attempts,
            "latency_ms": latency_ms,
            "error": str(last_err) if last_err else None,
        })
        return result

    # ----------------------------- internals --------------------------- #
    def _fallback_answer(self, message: str, hits: list[RetrievalHit],
                         has_kb: bool) -> dict:
        lang = detect_language(message)
        if has_kb:
            top = hits[0].doc
            answer = (f"Based on our information: {top.short_quote(140)}"
                      if lang == "en"
                      else "根据我们知识库中的相关资料，我们可以满足您的需求，具体依据见所引用的知识库条目。")
            need_human = False
            confidence = 0.4
        else:
            answer = ("This is outside the information I currently have; a human "
                      "colleague will follow up." if lang == "en"
                      else "该问题暂不在我们的资料范围内，将由同事人工跟进。")
            need_human = True
            confidence = 0.3
        return {
            "answer": answer,
            "language": lang,
            "confidence": confidence,
            "sources": [{"id": h.doc.id, "quote": h.doc.short_quote(120)} for h in hits[:3]],
            "need_human": need_human,
            "lead_fields": {},
            "follow_up_questions": [
                "Could you share more details (drawing, quantity, material)?"
            ],
        }

    def _normalize(self, parsed: dict, message: str, hits: list[RetrievalHit],
                   has_kb: bool, visitor: dict, prior_lead: dict,
                   trace_id: str) -> dict:
        out: dict = {}
        out["answer"] = str(parsed.get("answer") or "").strip() or \
            "Sorry, I could not generate an answer. A colleague will follow up."

        # language 以访客消息的实际语言为准（镜像），不盲信模型自报，避免"标 zh 却答英文"
        out["language"] = detect_language(message)

        try:
            conf = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        out["confidence"] = max(0.0, min(1.0, conf))

        # sources：只保留知识库中真实存在的 id，杜绝编造证据
        sources = []
        for s in parsed.get("sources") or []:
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id", "")).strip()
            doc = self.kb.get(sid)
            if doc:
                quote = str(s.get("quote") or "").strip() or doc.short_quote(120)
                sources.append({"id": sid, "quote": quote})
        if not sources and hits:
            sources = [{"id": h.doc.id, "quote": h.doc.short_quote(120)} for h in hits[:2]]
        out["sources"] = sources

        # need_human：知识库无依据时强制 true（情况 2）
        need_human = bool(parsed.get("need_human", False))
        if not has_kb or not sources:
            need_human = True
        out["need_human"] = need_human

        # lead_fields：规则抽取 + LLM 抽取 + 多轮累积（基于已持久化的历史线索）
        rule_lead = extract_lead(message, visitor)
        llm_lead = parsed.get("lead_fields") if isinstance(parsed.get("lead_fields"), dict) else {}
        merged = merge_leads(rule_lead, llm_lead)
        out["lead_fields"] = merge_leads(prior_lead, merged)

        # follow_up_questions：由"线索缺口"驱动精准发问（统一 mock 与真实 LLM）——
        # 只要可回答或已收集到任何线索，就按累积线索里仍缺的字段提问，字段齐全则转为确认报价；
        # 仅当完全越界且毫无线索信号时，才退回 LLM/默认的泛化澄清问题。
        lead_has_progress = any(v not in (None, "") for v in out["lead_fields"].values())
        if not need_human or lead_has_progress:
            out["follow_up_questions"] = followups_from_lead(
                out["lead_fields"], out["language"])
        else:
            fqs = parsed.get("follow_up_questions")
            out["follow_up_questions"] = [str(q) for q in fqs] if isinstance(fqs, list) and fqs else \
                (["Could you share more detail about your requirement so a colleague can help?"]
                 if out["language"] == "en"
                 else ["能否补充更多需求细节，方便同事为您跟进？"])

        out["trace_id"] = parsed.get("trace_id") or trace_id
        return out

    # ----------------------------- 运行时切换模型 ----------------------- #
    def deepseek_available(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    def switch_mode(self, mode: str) -> str:
        """在 mock / deepseek 之间运行时切换，返回实际生效的模式。"""
        mode = (mode or "").strip().lower()
        if mode not in ("mock", "deepseek"):
            raise ValueError(f"unsupported mode: {mode}")
        if mode == "deepseek" and not self.settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        self.settings.llm_mode = mode
        self.llm = build_llm(self.settings)
        return self.llm.name

    # ----------------------------- 会话查询 ----------------------------- #
    def export_lead(self, session_id: str) -> dict | None:
        sess = self.store.get_session(session_id)
        if not sess:
            return None
        return {"session_id": session_id, "lead_fields": sess["lead_fields"]}

    def list_sessions(self, limit: int = 50) -> list[dict]:
        return self.store.list_sessions(limit)

    def get_session(self, session_id: str) -> dict | None:
        return self.store.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self.store.delete_session(session_id)
