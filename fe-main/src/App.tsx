import { useEffect, useMemo, useState } from "react";
import {
  deleteSession,
  getHealth,
  getSession,
  isChatError,
  listSessions,
  postChat,
  setModel,
  type ChatResponse,
  type HealthResponse,
  type LeadFields,
  type SessionSummary,
} from "./api";
import {
  Analysis,
  AutoScroll,
  Evidence,
  LeadAccumulation,
  Panel,
  RecentList,
  TraceViewer,
  TranslatableAnswer,
  VisitorProfile,
  type AgentData,
} from "./components";
import { KnowledgeView, LeadsView, TraceView, type TraceTurn } from "./views";
import { timeHM, uuid } from "./util";

type Tab = "chat" | "leads" | "knowledge" | "trace";

type ChatMsg =
  | { role: "visitor"; text: string; ts?: string }
  | { role: "agent"; text: string; ts?: string; data: AgentData }
  | { role: "error"; text: string; code: string; ts?: string };

const EMPTY_LEAD: LeadFields = {
  product: null, quantity: null, country: null,
  email: null, material: null, drawing_available: null,
};

const DEMO = [
  "Can you make custom stainless steel brackets based on my drawing?",
  "What is the MOQ for CNC aluminum parts?",
  "Do you offer powder coating services?",
  "What are your payment terms?",
  "你们碳钢支架的最小起订量是多少？需要发到墨西哥",
];

const TABS: { key: Tab; zh: string; en: string; icon: string }[] = [
  { key: "chat", zh: "对话", en: "Chat", icon: "💬" },
  { key: "leads", zh: "线索", en: "Leads", icon: "📊" },
  { key: "knowledge", zh: "知识库", en: "Knowledge", icon: "📚" },
  { key: "trace", zh: "追踪", en: "Trace", icon: "🔎" },
];

function liveToData(r: ChatResponse): AgentData {
  return {
    language: r.language,
    confidence: r.confidence,
    sources: r.sources,
    need_human: r.need_human,
    follow_up_questions: r.follow_up_questions,
    trace_id: r.trace_id,
    latency_ms: r.meta?.latency_ms,
    retrieved: r.meta?.retrieved,
    kb_total: r.meta?.kb_total,
    degraded: r.meta?.degraded,
  };
}

function storedToData(meta: Record<string, unknown>): AgentData {
  return {
    language: String(meta.language ?? "en"),
    confidence: Number(meta.confidence ?? 0),
    sources: (meta.sources as AgentData["sources"]) ?? [],
    need_human: Boolean(meta.need_human),
    follow_up_questions: (meta.follow_up_questions as string[]) ?? [],
    trace_id: String(meta.trace_id ?? ""),
    latency_ms: meta.latency_ms as number | undefined,
    retrieved: meta.retrieved as AgentData["retrieved"],
    kb_total: meta.kb_total as number | undefined,
    degraded: meta.degraded as boolean | undefined,
    llm_raw_output: meta.llm_raw_output as string | undefined,
  };
}

export default function App() {
  const [tab, setTab] = useState<Tab>("chat");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionId, setSessionId] = useState(uuid());
  const [country, setCountry] = useState("Germany");
  const [email, setEmail] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [lead, setLead] = useState<LeadFields>(EMPTY_LEAD);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const lastAgent = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "agent") return m.data;
    }
    return null;
  }, [messages]);

  const traceTurns = useMemo<TraceTurn[]>(() => {
    const out: TraceTurn[] = [];
    let lastQ = "";
    for (const m of messages) {
      if (m.role === "visitor") lastQ = m.text;
      else if (m.role === "agent") out.push({ ...m.data, question: lastQ });
    }
    return out;
  }, [messages]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    refreshSessions();
  }, []);

  function refreshSessions() {
    listSessions().then(setSessions).catch(() => {});
  }

  async function changeModel(mode: "mock" | "deepseek") {
    if (health?.llm_mode === mode) return;
    const res = await setModel(mode);
    if (res.error) {
      alert("切换失败：" + res.error);
      return;
    }
    getHealth().then(setHealth).catch(() => {});
  }

  async function loadSession(id: string) {
    const res = await getSession(id);
    if (isChatError(res)) return;
    setSessionId(res.id);
    setCountry(res.visitor.country ?? "");
    setEmail(res.visitor.email ?? "");
    setLead(res.lead_fields ?? EMPTY_LEAD);
    setMessages(
      res.messages.map((m): ChatMsg =>
        m.role === "agent"
          ? { role: "agent", text: m.content, ts: m.ts, data: storedToData(m.meta) }
          : { role: "visitor", text: m.content, ts: m.ts }
      )
    );
    setTab("chat");
  }

  function newChat() {
    setSessionId(uuid());
    setMessages([]);
    setLead(EMPTY_LEAD);
    setTab("chat");
  }

  async function removeSession(id: string) {
    await deleteSession(id);
    if (id === sessionId) newChat();
    refreshSessions();
  }

  async function send(text: string) {
    const message = text.trim();
    setInput("");
    setTab("chat");
    setMessages((m) => [...m, { role: "visitor", text: message || "(空输入)", ts: new Date().toISOString() }]);
    setLoading(true);
    try {
      const res = await postChat({ session_id: sessionId, message, visitor: { country, email } });
      if (!res.ok || isChatError(res.data)) {
        const err = res.data as { error_code: string; error: string };
        setMessages((m) => [...m, { role: "error", text: err.error, code: err.error_code, ts: new Date().toISOString() }]);
      } else {
        const data = res.data as ChatResponse;
        setMessages((m) => [...m, { role: "agent", text: data.answer, ts: new Date().toISOString(), data: liveToData(data) }]);
        setLead(data.lead_fields);
        refreshSessions();
      }
    } catch (e) {
      setMessages((m) => [...m, { role: "error", text: String(e), code: "NETWORK", ts: new Date().toISOString() }]);
    } finally {
      setLoading(false);
    }
  }

  function exportLead() {
    const blob = new Blob(
      [JSON.stringify({ session_id: sessionId, lead_fields: lead }, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `lead-${sessionId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app">
      {/* ---------------- 顶部导航 ---------------- */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-logo">JH</div>
          <div>
            <div className="brand-title">外贸独立站客服 Agent</div>
            <div className="brand-sub">Customer-Service Console</div>
          </div>
        </div>
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`tab ${tab === t.key ? "active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              <span className="tab-icon">{t.icon}</span> {t.zh} <span className="tab-en">{t.en}</span>
            </button>
          ))}
        </nav>
        <div className="topbar-status">
          <span className={`chip ${health ? "chip-ok" : "chip-err"}`}>
            ● {health ? "在线 Online" : "离线 Offline"}
          </span>
          <label className="chip chip-model">
            模型:
            <select
              className="model-select"
              value={health?.llm_mode === "deepseek" ? "deepseek" : "mock"}
              onChange={(e) => changeModel(e.target.value as "mock" | "deepseek")}
            >
              <option value="deepseek" disabled={!health?.deepseek_available}>
                DeepSeek 实时{health?.deepseek_available ? "" : "（未配置 key）"}
              </option>
              <option value="mock">Mock 模式</option>
            </select>
          </label>
          <span className="chip chip-muted">📖 知识库 {health?.kb_docs ?? "—"} 条</span>
          <div className="avatar">JH</div>
        </div>
      </header>

      {/* ---------------- 主体 ---------------- */}
      {tab === "chat" ? (
        <div className={`layout ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
          {/* 左栏：可收起为图标条（ChatGPT 风格） */}
          {!sidebarOpen ? (
            <aside className="sidebar-rail">
              <button className="icon-btn" title="展开侧栏" onClick={() => setSidebarOpen(true)}>
                ☰
              </button>
              <button className="icon-btn rail-new" title="新建会话" onClick={newChat}>
                ＋
              </button>
            </aside>
          ) : (
          <aside className="sidebar">
            <div className="sidebar-top">
              <button className="btn btn-primary new-chat" onClick={newChat}>
                ＋ 新建会话 New Chat
              </button>
              <button className="icon-btn collapse-btn" title="收起侧栏" onClick={() => setSidebarOpen(false)}>
                «
              </button>
            </div>
            <Panel title="最近会话" en="Recent Conversations">
              <RecentList
                sessions={sessions}
                activeId={sessionId}
                onSelect={loadSession}
                onDelete={removeSession}
              />
            </Panel>
            <Panel title="示例问题" en="Demo Questions">
              <div className="suggestions">
                {DEMO.map((s, i) => (
                  <button key={i} className="suggestion" onClick={() => send(s)}>
                    <span className="q-icon">?</span> {s}
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title="会话详情" en="Session Details">
              <label className="field">
                <span>访客国家 Country</span>
                <input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Germany" />
              </label>
              <label className="field">
                <span>访客邮箱 Email</span>
                <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="可选 Optional" />
              </label>
              <div className="sid-mini">
                Session ID: <code>{sessionId.slice(0, 8)}…{sessionId.slice(-8)}</code>
              </div>
            </Panel>
          </aside>
          )}

          {/* 中栏对话 */}
          <main className="chat">
            <AutoScroll deps={[messages, loading]}>
              {messages.length === 0 && (
                <div className="welcome">
                  <h2>👋 欢迎使用客服 Agent 控制台</h2>
                  <p>输入访客问题或点击左侧示例。回答会附带知识库证据、置信度与抽取的询盘线索，并自动保存为会话。</p>
                </div>
              )}
              {messages.map((m, i) => {
                if (m.role === "visitor")
                  return (
                    <div key={i} className="turn turn-visitor">
                      <div className="bubble bubble-visitor">{m.text}</div>
                      <div className="avatar avatar-sm">👤</div>
                    </div>
                  );
                if (m.role === "error")
                  return (
                    <div key={i} className="turn turn-agent">
                      <div className="avatar avatar-sm bot">🤖</div>
                      <div className="bubble bubble-error">
                        <div className="err-code">错误码 {m.code}</div>
                        {m.text}
                      </div>
                    </div>
                  );
                return (
                  <div key={i} className="turn turn-agent">
                    <div className="avatar avatar-sm bot">🤖</div>
                    <div className="agent-block">
                      <div className="agent-meta-row">
                        <span className="ts">{timeHM(m.ts)}</span>
                        <span className={`badge ${m.data.need_human ? "badge-danger" : "badge-success"}`}>
                          {m.data.need_human ? "● 需人工" : "● 自动回答"}
                        </span>
                        <span className="badge badge-neutral">{m.data.language === "zh" ? "中文" : "EN"}</span>
                        <span className="trace-inline">Trace ID: {m.data.trace_id.slice(0, 23)}</span>
                      </div>
                      <TranslatableAnswer text={m.text} language={m.data.language} />
                      {m.data.follow_up_questions.length > 0 && (
                        <div className="followups">
                          <span className="followups-label">💡 建议追问访客 Suggested questions for the visitor</span>
                          <div className="followups-chips">
                            {m.data.follow_up_questions.map((q, j) => (
                              <span key={j} className="followup-sug">{q}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
              {loading && (
                <div className="turn turn-agent">
                  <div className="avatar avatar-sm bot">🤖</div>
                  <div className="bubble bubble-agent">
                    <div className="typing"><span /><span /><span /></div>
                  </div>
                </div>
              )}
            </AutoScroll>

            <div className="composer">
              <div className="composer-input">
                <textarea
                  value={input}
                  placeholder="输入消息... / Enter your message..."
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send(input);
                    }
                  }}
                />
                <div className="composer-toolbar">
                  <span className="tool">📎 附件</span>
                  <span className="tool" onClick={() => setInput(DEMO[0])}>⚡ 快捷回复</span>
                  <span className="tool">🌐 翻译 EN</span>
                  <button className="btn btn-primary send" disabled={loading} onClick={() => send(input)}>
                    ✈ 发送 Send
                  </button>
                </div>
              </div>
            </div>
          </main>

          {/* 右侧分析：小按钮触发的抽屉 */}
          <button
            className={`inspector-fab ${inspectorOpen ? "hidden" : ""}`}
            onClick={() => setInspectorOpen(true)}
            title="本轮分析 / 证据 / 线索"
          >
            📊 <span>分析</span>
          </button>
          {inspectorOpen && (
            <div className="drawer-backdrop" onClick={() => setInspectorOpen(false)} />
          )}
          <aside className={`inspector drawer ${inspectorOpen ? "open" : ""}`}>
            <div className="drawer-head">
              <span className="drawer-title">会话面板 <em>Insights</em></span>
              <button className="icon-btn" title="收起" onClick={() => setInspectorOpen(false)}>
                ✕
              </button>
            </div>
            <Panel title="访客信息" en="Visitor Profile">
              <VisitorProfile country={country} email={email} sessionId={sessionId} />
            </Panel>
            <Panel title="本轮分析" en="Analysis">
              <Analysis data={lastAgent} />
            </Panel>
            <Panel title="知识库证据" en="Evidence">
              <Evidence data={lastAgent} />
            </Panel>
            <Panel title="线索汇总" en="Lead Accumulation">
              <LeadAccumulation lead={lead} onExport={exportLead} />
            </Panel>
            <Panel title="追踪日志" en="Trace Viewer" defaultOpen={false}>
              <TraceViewer data={lastAgent} />
            </Panel>
          </aside>
        </div>
      ) : (
        <div className="single-page">
          {tab === "knowledge" && <KnowledgeView />}
          {tab === "leads" && <LeadsView onOpen={loadSession} />}
          {tab === "trace" && <TraceView turns={traceTurns} />}
        </div>
      )}
    </div>
  );
}
