"""FastAPI 服务：POST /chat、GET /health、GET /lead/{session_id}、GET /（后台页）。

启动：
    uvicorn src.server:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .agent import Agent
from .errors import AgentError, INTERNAL_ERROR

app = FastAPI(title="Foreign Trade Customer Service Agent", version="1.0.0")

# 允许独立前端（fe-main，开发时跑在 5173）跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class Visitor(BaseModel):
    country: str | None = None
    email: str | None = None


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None)
    message: str = Field(default="")
    visitor: Visitor | None = None


@app.get("/health")
def health() -> dict:
    a = get_agent()
    return {"status": "ok", "llm_mode": a.llm.name, "kb_docs": len(a.kb.docs),
            "deepseek_available": a.deepseek_available()}


class ModelRequest(BaseModel):
    mode: str = Field(default="mock")  # mock | deepseek


@app.post("/model")
def set_model(req: ModelRequest):
    """运行时切换 LLM 模式（mock / deepseek）。deepseek 需已配置 API key。"""
    a = get_agent()
    try:
        mode = a.switch_mode(req.mode)
        return JSONResponse({"llm_mode": mode})
    except ValueError as exc:
        return JSONResponse({"error_code": "E4002", "error": str(exc)}, status_code=400)


@app.post("/chat")
def chat(req: ChatRequest):
    a = get_agent()
    visitor = req.visitor.model_dump() if req.visitor else {}
    try:
        result = a.chat(req.message, session_id=req.session_id, visitor=visitor)
        return JSONResponse(result)
    except AgentError as exc:
        return JSONResponse(exc.to_dict(), status_code=exc.error.http_status)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error_code": INTERNAL_ERROR.code, "error": f"{INTERNAL_ERROR.message} ({exc})"},
            status_code=INTERNAL_ERROR.http_status,
        )


class TranslateRequest(BaseModel):
    text: str = Field(default="")
    target: str = Field(default="en")  # en | zh


@app.post("/translate")
def translate(req: TranslateRequest):
    """把回答翻译成目标语言（中英互译）。真实模式走 DeepSeek，mock 模式原样返回并标记。"""
    from .llm import translate_text
    a = get_agent()
    try:
        return JSONResponse(translate_text(a.settings, req.text, req.target))
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            {"error_code": "E3003", "error": f"translation failed ({exc})"},
            status_code=200,
        )


@app.get("/kb")
def list_kb():
    """列出全部知识库条目（供前端「知识库」Tab 浏览）。"""
    a = get_agent()
    return JSONResponse({
        "kb_total": len(a.kb.docs),
        "items": [{"id": d.id, "kind": d.kind, "title": d.title,
                   "text": d.text, "raw": d.raw} for d in a.kb.docs],
    })


@app.get("/kb/{doc_id}")
def get_kb_entry(doc_id: str):
    """按知识库 ID 返回该条的完整原始 JSON（供前端「展开原文」使用）。"""
    a = get_agent()
    doc = a.kb.get(doc_id)
    if doc is None:
        return JSONResponse({"error_code": "E4041", "error": "knowledge id not found"},
                            status_code=404)
    return JSONResponse({"id": doc.id, "kind": doc.kind, "raw": doc.raw})


@app.get("/lead/{session_id}")
def get_lead(session_id: str):
    a = get_agent()
    lead = a.export_lead(session_id)
    if lead is None:
        return JSONResponse({"error_code": "E4040", "error": "session not found"},
                            status_code=404)
    return JSONResponse(lead)


@app.get("/sessions")
def list_sessions(limit: int = 50):
    """最近会话列表（持久化）。"""
    return JSONResponse({"sessions": get_agent().list_sessions(limit)})


@app.get("/sessions/{session_id}")
def get_session(session_id: str):
    """单个会话的完整历史（消息 + 线索 + 访客 + 每轮 meta）。"""
    sess = get_agent().get_session(session_id)
    if sess is None:
        return JSONResponse({"error_code": "E4040", "error": "session not found"},
                            status_code=404)
    return JSONResponse(sess)


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    ok = get_agent().delete_session(session_id)
    if not ok:
        return JSONResponse({"error_code": "E4040", "error": "session not found"},
                            status_code=404)
    return JSONResponse({"deleted": session_id})


@app.get("/legacy", response_class=HTMLResponse)
def admin_page() -> str:
    """旧版极简内置后台（备用）。主前端见 fe-main（构建后挂载于 /）。"""
    return _ADMIN_HTML


_ADMIN_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>客服 Agent 后台</title>
<style>
 body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#1c2330}
 h1{font-size:20px}
 textarea,input{width:100%;box-sizing:border-box;padding:8px;font-size:14px;border:1px solid #cbd2dc;border-radius:6px}
 .row{display:flex;gap:8px;margin:8px 0}
 button{background:#2563eb;color:#fff;border:0;border-radius:6px;padding:9px 16px;font-size:14px;cursor:pointer}
 pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;font-size:13px}
 .lead{background:#f1f5f9;border-radius:8px;padding:10px 14px;font-size:13px}
 .badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px}
 .need{background:#fee2e2;color:#991b1b}.ok{background:#dcfce7;color:#166534}
</style></head><body>
<h1>外贸独立站客服 Agent — 后台演示</h1>
<div class="row"><input id="session" placeholder="session_id" value="web-demo"/>
 <input id="country" placeholder="country (optional)" value="Germany"/></div>
<textarea id="msg" rows="3" placeholder="Type a visitor question...">Can you make custom stainless steel brackets based on my drawing?</textarea>
<div class="row"><button onclick="send()">发送 / Send</button>
 <button onclick="loadLead()" style="background:#0891b2">查看累积线索 Lead</button></div>
<div id="status"></div>
<h3>Answer</h3><div id="answer"></div>
<h3>Lead fields</h3><div class="lead" id="leadbox">—</div>
<h3>Raw JSON</h3><pre id="out">—</pre>
<script>
async function send(){
 const body={session_id:document.getElementById('session').value,
   message:document.getElementById('msg').value,
   visitor:{country:document.getElementById('country').value}};
 const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const j=await r.json();
 document.getElementById('out').textContent=JSON.stringify(j,null,2);
 document.getElementById('answer').textContent=j.answer||j.error||'';
 const nh=j.need_human;
 document.getElementById('status').innerHTML = nh===undefined?'' :
   '<span class="badge '+(nh?'need':'ok')+'">'+(nh?'need_human=true':'auto-answered')+'</span> '+
   'confidence='+(j.confidence??'-');
 document.getElementById('leadbox').textContent=JSON.stringify(j.lead_fields||{},null,2);
}
async function loadLead(){
 const s=document.getElementById('session').value;
 const r=await fetch('/lead/'+encodeURIComponent(s));
 const j=await r.json();
 document.getElementById('leadbox').textContent=JSON.stringify(j,null,2);
}
</script></body></html>
"""


# ---- 挂载已构建的 React 前端（fe-main/dist），存在时作为主页 "/" ----
# 同源提供，前端的 /chat、/health、/lead 请求无需代理或 CORS。
# 仓库已提交 dist，clone 后无需 Node 即可看到完整界面；改前端后用 `npm run build` 重新生成。
_FE_DIST = Path(__file__).resolve().parents[1] / "fe-main" / "dist"
if (_FE_DIST / "index.html").is_file():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(_FE_DIST), html=True), name="fe")
else:
    @app.get("/", response_class=HTMLResponse)
    def _no_dist() -> str:
        return (
            "<html><body style='font-family:system-ui;max-width:640px;margin:60px auto'>"
            "<h2>前端尚未构建</h2>"
            "<p>未找到 <code>fe-main/dist</code>。请先构建前端：</p>"
            "<pre>cd fe-main &amp;&amp; npm install &amp;&amp; npm run build</pre>"
            "<p>然后刷新本页。或使用免构建的内置后台："
            "<a href='/legacy'>/legacy</a>。</p></body></html>"
        )
