# 外贸独立站客服 Agent（A_foreign_trade_customer_service）

一个最小可运行的「外贸独立站客服 Agent」：基于内置企业/产品知识库回答访客问题，
**有据可依**（引用知识库 ID + 原文片段），**信息不足时不编造**（自动 `need_human=true`
并收集线索），同时支持 **CLI** 与 **HTTP API** 两种入口。

> 原始作业要求保存在 [`docs/ASSIGNMENT.md`](docs/ASSIGNMENT.md)。

---

## 0. 克隆即跑（最快路径，无需 Node）

仓库已提交前端构建产物 `fe-main/dist`，且会话库 SQLite 首次运行自动创建，**只需 Python 即可跑起完整界面**。

### 一键脚本（推荐）

自动建 venv → 装依赖 →（有 Node 就）构建前端 → 启动后端（构建失败会自动回退到已提交的 dist，不影响启动）：

```bash
# Windows PowerShell
./start.ps1

# macOS / Linux
chmod +x start.sh && ./start.sh
# 自定义端口： ./start.sh --port 9000
```

### 或手动三步

```bash
git clone https://github.com/Billerhwq/Customer-Agent.git && cd Customer-Agent
python -m venv .venv && . .venv/Scripts/activate     # mac/linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                                         # 等价于 uvicorn src.server:app
# 浏览器打开 http://127.0.0.1:8000/
```

默认 `mock` 模式，无需任何 API key。要改前端再 `cd fe-main && npm install && npm run build`。

### 想看真实 DeepSeek 效果？（填自己的 key，3 步）

mock 模式已能跑通全部主流程，但回答语言不如真实 LLM 自然。要体验真实 DeepSeek，**填你自己的 key 即可**（仓库不含任何真实 key，出于安全不会内置）：

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

然后编辑 `.env`，把 mock 改成 deepseek 并填上你的 key：

```ini
LLM_MODE=deepseek
DEEPSEEK_API_KEY=sk-你自己的key      # 在 https://platform.deepseek.com 注册即可获取，有免费额度
```

重新运行 `./start.ps1`（或 `./start.sh`）即可。`.env` 已被 `.gitignore` 忽略，**不会被提交**。
> 也可以不改 `.env`：启动后在**前端顶部下拉运行时切换** mock / DeepSeek（未配置 key 时 deepseek 选项自动置灰）。

## 1. 安装依赖

需要 Python 3.10+（开发环境为 3.13）。

```bash
# 1. 创建并激活虚拟环境
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 准备环境变量（默认 mock 模式，无需任何 key）
cp .env.example .env      # Windows: copy .env.example .env
```

`.env` 已被 `.gitignore` 忽略，**仓库中不含任何真实 API key**。会话数据保存在 `data/app.db`（SQLite，自动创建、已被忽略不入库）。

## 2. 如何启动

### 2.1 CLI

```bash
python app.py "Can you make custom stainless steel brackets based on my drawing?"

# 带会话 ID（多轮线索累积）和访客信息
python app.py --session demo-001 --country Germany "What is the MOQ for CNC aluminum parts?"
```

输出为合法 JSON（UTF-8）。空输入会返回错误码 `E1001` 并以退出码 1 结束（不会崩溃）。

### 2.2 HTTP API

```bash
uvicorn src.server:app --reload --port 8000
```

- `POST /chat` — 主接口（响应含规范 8 字段 + 额外 `meta` UI 遥测：用时/检索命中/模式）
- `GET  /health` — 健康检查（返回当前 LLM 模式、知识库条数）
- `GET  /lead/{session_id}` — 导出某会话累积的高价值询盘线索（lead JSON）
- `GET  /sessions` — **最近会话列表**（持久化，按更新时间倒序）
- `GET  /sessions/{id}` — 单个会话完整历史（消息 + 线索 + 访客 + 每轮 meta）
- `DELETE /sessions/{id}` — 删除会话
- `GET  /kb` — 列出全部知识库条目；`GET /kb/{id}` — 单条完整原文
- `POST /model` — 运行时切换 LLM 模式（`mock` / `deepseek`），无需重启
- `POST /translate` — 把回答中英互译（真实模式走 DeepSeek，mock 模式原样返回并标记）
- `GET  /` — **企业级控制台前端**（React，见 `fe-main`；已提交 dist，由后端同源挂载）
- `GET  /legacy` — 内置极简后台（无需构建的备用演示页）

### 2.3 前端控制台（fe-main）

`fe-main/` 是一个基于 **React 18 + TypeScript + Vite** 的企业级控制台，把对话、知识库证据、
置信度、`need_human`、累积线索、错误码等全部可视化。

```bash
cd fe-main && npm install && npm run build   # 产物输出到 fe-main/dist
cd .. && uvicorn src.server:app --port 8000  # 浏览器打开 http://127.0.0.1:8000/
```

后端会自动挂载 `fe-main/dist`，**同源访问、无需代理或额外服务**。开发模式（热更新）见
[`fe-main/README.md`](fe-main/README.md)。

请求示例：

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","message":"Can you make custom stainless steel brackets based on my drawing?","visitor":{"country":"Germany","email":""}}'
```

响应（节选）：

```json
{
  "answer": "Based on our information: custom stamping bracket ... For a quotation, please share drawing, material, quantity, surface treatment, tolerance, and destination country.",
  "language": "en",
  "confidence": 0.95,
  "sources": [{"id": "P001", "quote": "custom stamping bracket. Materials: stainless steel..."}],
  "need_human": false,
  "lead_fields": {"product": "bracket", "quantity": null, "country": "Germany",
                  "email": null, "material": "stainless steel", "drawing_available": true},
  "follow_up_questions": ["Could you share the drawing or STEP file?", "What quantity do you need?"],
  "trace_id": "trace-demo-001-0002de69"
}
```

输出字段严格符合 [`schema/output_schema.json`](schema/output_schema.json)。

## 3. 如何运行测试

```bash
# 单元测试（覆盖作业 §5 的 6 种必须处理情况 + 加分项，纯 mock，无需 key）
python -m pytest -q

# 跑作业指定的 5 条用例并把每条输出保存到 tests/outputs/
python tests/run_tests.py
```

`python tests/run_tests.py` 会在控制台打印每条用例的回答、`need_human`、引用的知识库 ID、
抽取到的线索，并把完整 JSON 写入 `tests/outputs/T00X.json`，可复现。

当前 5 条用例的行为（mock 模式）：

| 用例 | 问题 | need_human | 引用 | 关键线索 |
|------|------|------------|------|----------|
| T001 | 不锈钢支架定制 | false | P001/P003/F002 | product=bracket, material=stainless steel, drawing=true |
| T002 | CNC 铝件 MOQ | false | P002 | material=aluminum |
| T003 | 30 个样品下周发德国 | **true**（不承诺） | F001/F004 | quantity=30, country=Germany |
| T004 | 是否卖塑料玩具 | **true**（超出范围） | — | — |
| T005 | 2000 碳钢支架发墨西哥报价 | false | P001/P003/F003 | quantity=2000, material=carbon steel, country=Mexico, product=bracket |

## 4. 是否使用真实 LLM / 如何切换 mock

**两种模式都支持，由 `.env` 中的 `LLM_MODE` 控制：**

- `LLM_MODE=mock`（**默认**）：不调用任何外部 API，基于检索结果用规则生成结构化回答。
  保证评审方没有 key 也能跑通全部主流程与测试。
- `LLM_MODE=deepseek`：调用真实 **DeepSeek**（OpenAI 兼容的 `/chat/completions` 接口），
  需在 `.env` 配置：

  ```ini
  LLM_MODE=deepseek
  DEEPSEEK_API_KEY=sk-xxxx
  DEEPSEEK_BASE_URL=https://api.deepseek.com
  DEEPSEEK_MODEL=deepseek-chat
  ```

除 `.env` 外，**前端顶部下拉可在运行时一键切换 mock / DeepSeek**（调用 `POST /model`，未配置
key 时 deepseek 选项自动置灰）。

无论哪种模式，LLM 的输出都会经过统一的 **JSON 解析 / 修复 / 重试 / 降级** 管线
（见 [`src/json_repair.py`](src/json_repair.py) 与 [`src/agent.py`](src/agent.py)）：
若返回非法 JSON，先尝试剥离代码块围栏、截取大括号、修正尾随逗号等；重试 `LLM_MAX_RETRIES`
次仍失败，则**降级**为基于检索的规则回答，绝不让请求崩溃，并在日志中标记 `degraded=true`
（前端「追踪日志」面板与 `logs/traces.jsonl` 均可见 `degraded` / `error_code` / `attempts`）。

## 5. 用到的 AI coding 工具

- **Claude Code（claude-opus）**：用于完成本项目的架构设计与全部代码编写、调试。

## 6. 哪些代码/设计是我自己完成或修改的

整个应用层代码均为本项目实现，关键设计决策：

- **检索相关性判定**：BM25 排序分经过 max 归一化后，对最相关文档恒为 1.0，无法用于阈值
  判断「知识库是否真的有答案」。因此额外引入**实义词覆盖率（coverage）**作为相关性闸门
  （去停用词 + 简单复数还原），使「塑料玩具」这类越界问题能被正确判为 `need_human=true`。
  见 [`src/retrieval.py`](src/retrieval.py)。
- **证据防伪**：`sources` 中的 `id` 会与知识库实际存在的 ID 校验，杜绝 LLM 编造引用；
  无有效证据时强制 `need_human=true`。见 [`src/agent.py`](src/agent.py) 的 `_normalize`。
- **线索抽取**：规则抽取（正则 + 词典，带词边界匹配，避免 `US` 命中 `custom`）与 LLM 抽取
  结果合并，并支持**多轮累积**。见 [`src/lead_extraction.py`](src/lead_extraction.py)。
- **追问由"线索缺口"驱动**：`follow_up_questions` 不是静态模板，而是按累积线索里**仍缺失的字段**
  （按对报价的重要性排序）动态发问，已填字段自动不再问；6 个字段齐全后转为"是否整理正式报价单"。
  统一作用于 mock 与真实 LLM，把对话变成驱动线索补全的销售漏斗。见
  `followups_from_lead` + [`src/agent.py`](src/agent.py) `_normalize`。
- **会话持久化**：用零依赖的 SQLite（`src/store.py`）保存会话/消息/累积线索/每轮 meta，
  进程重启后「最近会话 / 历史 / 线索」依然可用；`/sessions` 系列接口与前端最近会话侧栏由此驱动。
- **回答语言镜像**：按 `detect_language(访客消息)` 在提示词里**硬性指定回答语言**并以此确定
  `language` 字段——中文问中文答、英文问英文答（"优先英文"是默认/兜底），消除"标 zh 却答英文"的不一致。
- **每条回答中英互译**：`POST /translate` + 前端按答案实际文字判断方向；以及**运行时切换 mock/DeepSeek**。
- **错误码体系**、**结构化追踪日志**均为自定义实现。

## 7. 已知限制

- mock 模式的回答是基于模板/检索拼接的，语言自然度不如真实 LLM；它的价值在于保证主流程、
  证据引用、JSON 稳定性与降级路径可被无 key 复现。**特别地**：知识库为英文且 mock 不翻译，
  故中文提问下 mock 只能给"纯中文但较通用"的回答（要带具体数字的自然中文回答请切 DeepSeek）。
- 检索为轻量 BM25 + 覆盖率，未使用向量检索；知识库规模很小时已足够，但同义改写（如
  "minimum order" vs "MOQ"）的召回有限。
- 中文支持采用字符 bigram + 词典，未接入分词库，复杂中文长句的检索召回一般。
- 会话已持久化到 SQLite（单机文件库），适合演示/单实例；多实例横向扩展需换成共享数据库。
- 线索字段的词典是面向当前知识库（金属加工）手工维护的，换行业需扩充词典或改用 LLM 抽取。
- 会话标题用首条消息截断生成（非 LLM 摘要），够用但不够"聪明"。

---

## 项目结构

```text
A_foreign_trade_customer_service/
├── README.md                 # 本文件
├── .env.example              # 环境变量示例（不含真实 key）
├── requirements.txt
├── run.py                    # 一键启动（python run.py）
├── app.py                    # CLI 入口
├── src/
│   ├── config.py             # 配置加载
│   ├── errors.py             # 错误码
│   ├── knowledge_base.py     # 知识库加载（保留每条 id）
│   ├── retrieval.py          # BM25 + 覆盖率检索 + 中英术语桥接
│   ├── language.py           # 中英语言检测
│   ├── lead_extraction.py    # 询盘线索抽取 + 多轮累积
│   ├── prompts.py            # LLM 提示词
│   ├── llm.py                # mock + DeepSeek 客户端
│   ├── json_repair.py        # 非法 JSON 解析/修复
│   ├── store.py              # SQLite 会话持久化
│   ├── agent.py              # 编排核心（检索→LLM→修复→降级→校验→持久化）
│   ├── logging_utils.py      # traces.jsonl 结构化日志
│   └── server.py             # FastAPI: /chat /health /lead /sessions /kb + 挂载前端
├── fe-main/                  # React + TS + Vite 企业级控制台前端（已提交 dist）
│   ├── src/{App.tsx,api.ts,components.tsx,views.tsx,util.ts,styles.css}
│   ├── dist/                 # 构建产物（提交以便 clone 即跑）
│   └── README.md
├── knowledge/company_knowledge.json
├── schema/output_schema.json
├── tests/{test_cases.json, test_agent.py, run_tests.py}
├── docs/ASSIGNMENT.md        # 原始作业要求
├── data/app.db               # SQLite 会话库（运行时生成，不入库）
└── logs/traces.jsonl         # 运行后生成
```

## 加分项落实情况

- [x] 多轮对话中的线索累积（`session_id` + **SQLite 持久化**，重启不丢）
- [x] 中英文问题（自动语言检测 + 中→英术语桥接，回答语言镜像访客）
- [x] 高价值询盘输出为 lead JSON（`GET /lead/{session_id}` + 前端导出按钮）
- [x] 后台页面（`fe-main`：四 Tab 企业级 React 控制台 — 对话/线索/知识库/追踪，含最近会话历史、证据展开、分析仪表、追踪日志）
- [x] 清晰的错误码（`src/errors.py`，如 `E1001` 空输入）
- [x] 单元测试（`pytest`，14 个用例）
- [x] **会话历史与持久化**（最近会话列表、历史回放、删除；`/sessions` 系列接口 + SQLite）
- [x] **每条回答中英互译** + **运行时切换 mock/DeepSeek**（前端顶部下拉）
