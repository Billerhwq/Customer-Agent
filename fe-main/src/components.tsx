import { useEffect, useRef, useState } from "react";
import {
  getKbEntry,
  isChatError,
  translate,
  type LeadFields,
  type RetrievedHit,
  type SessionSummary,
  type Source,
} from "./api";
import {
  confidenceTier,
  copyText,
  flagOf,
  LEAD_LABELS,
  leadFilledCount,
  relativeDay,
} from "./util";

/* 派生的「本轮分析」数据（来自最后一条 agent 消息） */
export interface AgentData {
  language: string;
  confidence: number;
  sources: Source[];
  need_human: boolean;
  follow_up_questions: string[];
  trace_id: string;
  latency_ms?: number;
  retrieved?: RetrievedHit[];
  kb_total?: number;
  degraded?: boolean;
  llm_raw_output?: string;
}

/* ---------- 可翻译的回答气泡（中英互译） ---------- */
export function TranslatableAnswer({ text }: { text: string; language?: string }) {
  // 以实际文字判断语言：含中日韩字符即视为中文，提供翻译为英文；否则翻译为中文。
  const isCjk = /[一-鿿]/.test(text);
  const target: "en" | "zh" = isCjk ? "en" : "zh";
  const targetLabel = target === "en" ? "English" : "中文";
  const [translated, setTranslated] = useState<string | null>(null);
  const [showTrans, setShowTrans] = useState(false);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function toggle() {
    if (showTrans) {
      setShowTrans(false);
      return;
    }
    if (translated === null) {
      setLoading(true);
      setNote(null);
      try {
        const res = await translate(text, target);
        setTranslated(res.text);
        if (res.mocked) setNote("（mock 模式不联网，未真正翻译；切换 DeepSeek 后可用）");
      } catch (e) {
        setNote("翻译失败：" + String(e));
      } finally {
        setLoading(false);
      }
    }
    setShowTrans(true);
  }

  return (
    <div className="bubble bubble-agent">
      <div className="answer-text">{showTrans && translated ? translated : text}</div>
      {showTrans && note && <div className="trans-note">{note}</div>}
      <button className="translate-btn" onClick={toggle} disabled={loading}>
        {loading ? "翻译中…" : showTrans ? "↩ 显示原文" : `🌐 翻译为${targetLabel}`}
      </button>
    </div>
  );
}

/* ---------- 通用卡片（可折叠） ---------- */
export function Panel({
  title,
  en,
  extra,
  defaultOpen = true,
  children,
}: {
  title: string;
  en?: string;
  extra?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="panel">
      <header className="panel-head">
        <button className="panel-title" onClick={() => setOpen((o) => !o)}>
          <span className="panel-zh">{title}</span>
          {en && <span className="panel-en">{en}</span>}
        </button>
        <div className="panel-extra">
          {extra}
          <button className="panel-caret" onClick={() => setOpen((o) => !o)}>
            {open ? "⌃" : "⌄"}
          </button>
        </div>
      </header>
      {open && <div className="panel-body">{children}</div>}
    </section>
  );
}

/* ---------- 置信度环形仪表 ---------- */
export function Gauge({ value, size = 84 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const hue = value >= 0.7 ? 152 : value >= 0.4 ? 38 : 0;
  const color = `hsl(${hue} 68% 45%)`;
  const r = size / 2 - 8;
  const c = 2 * Math.PI * r;
  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} className="gauge-track" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="gauge-value"
          stroke={color}
          strokeDasharray={`${c * value} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="gauge-label">
        <span className="gauge-num" style={{ color }}>
          {pct}
        </span>
        <span className="gauge-unit">%</span>
      </div>
    </div>
  );
}

/* ---------- 最近会话列表 ---------- */
export function RecentList({
  sessions,
  activeId,
  onSelect,
  onDelete,
}: {
  sessions: SessionSummary[];
  activeId: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  if (!sessions.length)
    return <div className="empty-hint">还没有会话，发送第一条消息即可创建。</div>;
  return (
    <ul className="recent-list">
      {sessions.map((s) => (
        <li
          key={s.id}
          className={`recent-item ${s.id === activeId ? "active" : ""}`}
          onClick={() => onSelect(s.id)}
        >
          <div className="recent-main">
            <div className="recent-title">{s.title}</div>
            <div className="recent-preview">{s.preview}</div>
          </div>
          <div className="recent-meta">
            <span className="recent-time">{relativeDay(s.updated_at)}</span>
            {s.lead_completeness > 0 && (
              <span className="recent-dot" title={`线索 ${s.lead_completeness}/6`} />
            )}
          </div>
          <button
            className="recent-del"
            title="删除会话"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(s.id);
            }}
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}

/* ---------- 访客信息 ---------- */
export function VisitorProfile({
  country,
  email,
  sessionId,
}: {
  country?: string | null;
  email?: string | null;
  sessionId: string;
}) {
  return (
    <div className="visitor">
      <div className="visitor-row">
        <div className="visitor-cell">
          <span className="vk">国家 Country</span>
          <span className="vv">
            {flagOf(country)} {country || "未知"}
          </span>
        </div>
        <div className="visitor-cell">
          <span className="vk">邮箱 Email</span>
          <span className="vv">{email || "可选 Optional"}</span>
        </div>
      </div>
      <div className="session-id-row">
        <span className="vk">Session ID</span>
        <code className="sid">{sessionId}</code>
        <button className="copy-btn" title="复制" onClick={() => copyText(sessionId)}>
          ⧉
        </button>
      </div>
    </div>
  );
}

/* ---------- 本轮分析 ---------- */
export function Analysis({ data }: { data: AgentData | null }) {
  if (!data) return <div className="empty-hint">发送一条消息后展示置信度、召回与用时。</div>;
  const tier = confidenceTier(data.confidence);
  const hits = data.retrieved?.length ?? data.sources.length;
  const total = data.kb_total ?? 9;
  const metrics = [
    {
      k: "置信度 Confidence",
      v: `${Math.round(data.confidence * 100)}%`,
      tag: <span className={`tier ${tier.cls}`}>{tier.label}</span>,
      dot: "#2563eb",
    },
    { k: "召回 Recall", v: data.sources.length ? "是" : "否", dot: "#16a34a" },
    {
      k: "模型用时 Time",
      v: data.latency_ms != null ? `${(data.latency_ms / 1000).toFixed(1)}s` : "—",
      dot: "#d97706",
    },
    { k: "知识库命中 Entries", v: `${hits}/${total}`, dot: "#7c3aed" },
  ];
  return (
    <div className="analysis">
      <ul className="metrics">
        {metrics.map((m) => (
          <li key={m.k}>
            <span className="metric-dot" style={{ background: m.dot }} />
            <span className="metric-k">{m.k}</span>
            <span className="metric-v">
              {m.v} {m.tag}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- 知识库证据（单条，可展开完整 JSON） ---------- */
function EvidenceItem({ source, score }: { source: Source; score?: number }) {
  const [open, setOpen] = useState(false);
  const [raw, setRaw] = useState<Record<string, unknown> | null>(null);
  const KIND: Record<string, string> = { C: "#7c3aed", P: "#2563eb", F: "#0891b2" };
  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && raw === null) {
      const res = await getKbEntry(source.id);
      if (!isChatError(res)) setRaw(res.raw);
    }
  }
  return (
    <div className="evidence">
      <div className="evidence-head">
        <span className="ev-id" style={{ background: KIND[source.id[0]] ?? "#64748b" }}>
          {source.id}
        </span>
        <span className="ev-title">{rawTitle(source)}</span>
        {score != null && <span className="ev-score">{Math.round(score * 100)}%</span>}
      </div>
      <div className="ev-quote">“{source.quote}”</div>
      <button className="ev-more" onClick={toggle}>
        {open ? "收起" : "查看更多"}
      </button>
      {open && raw && <pre className="ev-raw">{JSON.stringify(raw, null, 2)}</pre>}
    </div>
  );
}
function rawTitle(s: Source): string {
  // quote 通常以名称/问题开头，截取首句作为标题
  const head = s.quote.split(/[.。:：]/)[0];
  return head.length > 30 ? head.slice(0, 29) + "…" : head;
}

export function Evidence({ data }: { data: AgentData | null }) {
  if (!data) return <div className="empty-hint">回答将引用知识库 ID 与原文片段作为证据。</div>;
  if (!data.sources.length)
    return <div className="empty-hint">本次回答未引用知识库证据，已标记需人工跟进。</div>;
  const scoreOf = (id: string) =>
    data.retrieved?.find((r) => r.id === id)?.score;
  return (
    <div className="evidence-list">
      {data.sources.map((s, i) => (
        <EvidenceItem key={`${s.id}-${i}`} source={s} score={scoreOf(s.id)} />
      ))}
    </div>
  );
}

/* ---------- 线索汇总 ---------- */
export function LeadAccumulation({
  lead,
  onExport,
}: {
  lead: LeadFields;
  onExport: () => void;
}) {
  const filled = leadFilledCount(lead);
  return (
    <div>
      <div className="lead-progress">
        <span>线索完整度</span>
        <div className="lead-bar">
          <div
            className="lead-bar-fill"
            style={{ width: `${(filled / LEAD_LABELS.length) * 100}%` }}
          />
        </div>
        <span className="lead-count">{filled}/{LEAD_LABELS.length}</span>
      </div>
      <dl className="lead-grid">
        {LEAD_LABELS.map(({ key, label }) => {
          const v = lead[key];
          const has = v !== null && v !== undefined && v !== "";
          const display =
            key === "drawing_available"
              ? v === true
                ? "是"
                : v === false
                ? "否"
                : "—"
              : has
              ? String(v)
              : "—";
          return (
            <div key={key} className={`lead-cell ${has ? "filled" : "blank"}`}>
              <dt>{label}</dt>
              <dd>{display}</dd>
            </div>
          );
        })}
      </dl>
      <button className="btn btn-mini lead-export" onClick={onExport}>
        导出 JSON
      </button>
    </div>
  );
}

/* ---------- 追踪日志 ---------- */
export function TraceViewer({ data }: { data: AgentData | null }) {
  const [open, setOpen] = useState(false);
  if (!data) return <div className="empty-hint">每轮请求的 trace_id、用时、降级状态与原始输出。</div>;
  return (
    <div className="trace">
      <div className="trace-row">
        <span className="trace-k">trace_id</span>
        <code className="trace-v">{data.trace_id}</code>
      </div>
      <div className="trace-row">
        <span className="trace-k">用时 / 降级</span>
        <span className="trace-v">
          {data.latency_ms != null ? `${data.latency_ms}ms` : "—"} ·{" "}
          {data.degraded ? "已降级" : "正常"}
        </span>
      </div>
      {data.llm_raw_output && (
        <>
          <button className="ev-more" onClick={() => setOpen((o) => !o)}>
            {open ? "收起 LLM 原始输出" : "查看 LLM 原始输出"}
          </button>
          {open && <pre className="ev-raw">{data.llm_raw_output}</pre>}
        </>
      )}
    </div>
  );
}

/* ---------- 自动滚动到底部的容器 ---------- */
export function AutoScroll({ deps, children }: { deps: unknown[]; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: 1e9, behavior: "smooth" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return (
    <div className="chat-scroll" ref={ref}>
      {children}
    </div>
  );
}
