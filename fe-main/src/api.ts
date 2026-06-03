// 与后端 FastAPI 的类型契约与请求封装。

export interface Source {
  id: string;
  quote: string;
}

export interface LeadFields {
  product: string | null;
  quantity: string | number | null;
  country: string | null;
  email: string | null;
  material: string | null;
  drawing_available: boolean | null;
}

export interface RetrievedHit {
  id: string;
  score: number;
  coverage: number;
}

export interface ChatMeta {
  latency_ms: number;
  llm_mode: string;
  degraded: boolean;
  error_code: string | null;
  kb_total: number;
  retrieved: RetrievedHit[];
  attempts: number;
}

export interface ChatResponse {
  answer: string;
  language: string;
  confidence: number;
  sources: Source[];
  need_human: boolean;
  lead_fields: LeadFields;
  follow_up_questions: string[];
  trace_id: string;
  meta: ChatMeta;
}

export interface ChatError {
  error_code: string;
  error: string;
}

export interface HealthResponse {
  status: string;
  llm_mode: string;
  kb_docs: number;
  deepseek_available: boolean;
}

export async function setModel(mode: "mock" | "deepseek"): Promise<{ llm_mode?: string; error?: string }> {
  const r = await fetch("/model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode }),
  });
  return r.json();
}

export interface Visitor {
  country?: string | null;
  email?: string | null;
}

export interface SessionSummary {
  id: string;
  title: string;
  preview: string;
  created_at: string;
  updated_at: string;
  country: string | null;
  message_count: number;
  lead_completeness: number;
}

export interface StoredMessage {
  role: "visitor" | "agent" | "error";
  content: string;
  meta: Record<string, unknown>;
  ts: string;
}

export interface SessionDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  visitor: Visitor;
  lead_fields: LeadFields;
  messages: StoredMessage[];
}

export interface KbItem {
  id: string;
  kind: string;
  title: string;
  text: string;
  raw: Record<string, unknown>;
}

export function isChatError(x: unknown): x is ChatError {
  return !!x && typeof x === "object" && "error_code" in (x as object);
}

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  return r.json();
}

export const getHealth = () => getJSON<HealthResponse>("/health");
export const listSessions = () =>
  getJSON<{ sessions: SessionSummary[] }>("/sessions").then((d) => d.sessions);
export const getSession = (id: string) =>
  getJSON<SessionDetail | ChatError>(`/sessions/${encodeURIComponent(id)}`);
export const listKb = () =>
  getJSON<{ kb_total: number; items: KbItem[] }>("/kb");
export const getKbEntry = (id: string) =>
  getJSON<KbItem | ChatError>(`/kb/${encodeURIComponent(id)}`);

export async function deleteSession(id: string): Promise<void> {
  await fetch(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export interface TranslateResult {
  text: string;
  target: string;
  mocked: boolean;
}

export async function translate(text: string, target: "en" | "zh"): Promise<TranslateResult> {
  const r = await fetch("/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target }),
  });
  return r.json();
}

export async function postChat(req: {
  session_id: string;
  message: string;
  visitor?: Visitor;
}): Promise<{ ok: boolean; status: number; data: ChatResponse | ChatError }> {
  const r = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  const data = await r.json();
  return { ok: r.ok, status: r.status, data };
}
