import { useEffect, useState } from "react";
import {
  listKb,
  listSessions,
  type KbItem,
  type SessionSummary,
} from "./api";
import { flagOf, relativeDay } from "./util";
import type { AgentData } from "./components";

/* ---------------- 知识库 Tab ---------------- */
const KIND_LABEL: Record<string, string> = {
  company: "公司", product: "产品", faq: "FAQ",
};
const KIND_COLOR: Record<string, string> = { C: "#7c3aed", P: "#2563eb", F: "#0891b2" };

export function KnowledgeView() {
  const [items, setItems] = useState<KbItem[]>([]);
  useEffect(() => {
    listKb().then((d) => setItems(d.items));
  }, []);
  return (
    <div className="tab-page">
      <h2 className="tab-title">知识库 Knowledge <span>{items.length} 条</span></h2>
      <p className="tab-sub">回答只依据以下内置资料，引用时保留每条 ID 作为证据来源。</p>
      <div className="kb-grid">
        {items.map((it) => (
          <div key={it.id} className="kb-card">
            <div className="kb-card-head">
              <span className="ev-id" style={{ background: KIND_COLOR[it.id[0]] ?? "#64748b" }}>
                {it.id}
              </span>
              <span className="kb-kind">{KIND_LABEL[it.kind] ?? it.kind}</span>
            </div>
            <div className="kb-card-title">{it.title}</div>
            <pre className="kb-raw">{JSON.stringify(it.raw, null, 2)}</pre>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------- 线索 Tab ---------------- */
export function LeadsView({ onOpen }: { onOpen: (id: string) => void }) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  useEffect(() => {
    listSessions().then(setSessions);
  }, []);
  return (
    <div className="tab-page">
      <h2 className="tab-title">询盘线索 Leads <span>{sessions.length} 个会话</span></h2>
      <p className="tab-sub">按会话汇总的高价值询盘；点击任意一行可回到对话查看完整线索与证据。</p>
      <table className="leads-table">
        <thead>
          <tr>
            <th>会话标题</th>
            <th>国家</th>
            <th>消息数</th>
            <th>线索完整度</th>
            <th>更新时间</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id} onClick={() => onOpen(s.id)}>
              <td>{s.title}</td>
              <td>{flagOf(s.country)} {s.country || "—"}</td>
              <td>{s.message_count}</td>
              <td>
                <div className="mini-bar">
                  <div style={{ width: `${(s.lead_completeness / 6) * 100}%` }} />
                </div>
                <span className="mini-count">{s.lead_completeness}/6</span>
              </td>
              <td>{relativeDay(s.updated_at)}</td>
            </tr>
          ))}
          {!sessions.length && (
            <tr>
              <td colSpan={5} className="empty-hint">暂无会话。</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------- 追踪 Tab ---------------- */
export interface TraceTurn extends AgentData {
  question: string;
}
export function TraceView({ turns }: { turns: TraceTurn[] }) {
  return (
    <div className="tab-page">
      <h2 className="tab-title">追踪 Trace <span>{turns.length} 轮</span></h2>
      <p className="tab-sub">当前会话每一轮的 trace_id、用时、检索命中、降级状态与 LLM 原始输出。</p>
      {!turns.length && <div className="empty-hint">当前会话还没有可追踪的轮次。</div>}
      <div className="trace-cards">
        {turns.map((t, i) => (
          <details key={i} className="trace-card">
            <summary>
              <code className="trace-v">{t.trace_id}</code>
              <span className="trace-tags">
                <span className="tag-blue">{t.latency_ms ?? "—"}ms</span>
                <span className={t.degraded ? "tag-red" : "tag-green"}>
                  {t.degraded ? "降级" : "正常"}
                </span>
                <span className="tag-gray">命中 {t.retrieved?.length ?? 0}</span>
              </span>
            </summary>
            <div className="trace-detail">
              <div className="trace-q">Q: {t.question}</div>
              <div className="trace-line">
                检索: {(t.retrieved ?? []).map((r) => `${r.id}(${r.score})`).join(", ") || "—"}
              </div>
              {t.llm_raw_output && (
                <pre className="ev-raw">{t.llm_raw_output}</pre>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
