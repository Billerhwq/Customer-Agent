# 二面小项目 A：外贸独立站客服 Agent

## 1. 项目背景

我们正在为制造业企业搭建外贸独立站。网站访客经常会询问：

- 是否支持 OEM / 定制加工
- MOQ 是多少
- 是否能根据图纸、样品或 3D 模型报价
- 材料、表面处理、交期、样品、发货方式
- 某些产品是否能做

希望你实现一个最小可运行的「外贸独立站客服 Agent」：它能基于内置企业/产品资料回答访客问题，并在信息不足时不编造答案，而是收集线索并建议人工跟进。

## 2. 完成时间

建议在 24-48 小时内完成。

如果时间不够，请优先保证核心链路能跑通，不要堆页面效果。

## 3. 技术要求

技术栈不限，推荐：

- Python + FastAPI / CLI
- Node.js + Express / CLI
- RAG 可以用关键词检索、BM25、向量检索中的任意一种
- LLM 可以调用真实 API，也可以用 mock 模式

必须注意：

- 不要提交真实 API key。
- 必须提供 `.env.example`。
- 如果使用真实大模型，也必须支持 mock 模式，保证我们没有 key 也能跑通主流程。

## 4. 必做功能

### 4.1 内置知识库

请使用本包里的 `knowledge/company_knowledge.json` 作为初始知识库。

你可以补充知识库内容，但必须保留每条信息的 `id`，便于输出引用证据。

### 4.2 输入

至少支持一种输入方式：

1. CLI：

```bash
python app.py "Can you make custom stainless steel brackets based on my drawing?"
```

2. HTTP API：

```http
POST /chat
Content-Type: application/json
```

示例输入：

```json
{
  "session_id": "demo-001",
  "message": "Can you make custom stainless steel brackets based on my drawing?",
  "visitor": {
    "country": "Germany",
    "email": ""
  }
}
```

### 4.3 输出

必须输出合法 JSON，字段至少包括：

```json
{
  "answer": "Yes, we support OEM custom stainless steel brackets based on drawings or samples. Please send your drawing, material, quantity, surface treatment, tolerance requirements, and destination country for quotation.",
  "language": "en",
  "confidence": 0.86,
  "sources": [
    {
      "id": "P001",
      "quote": "custom stamping bracket... drawing, sample, or 3D model accepted"
    },
    {
      "id": "F003",
      "quote": "Please provide drawing, material, quantity, surface treatment..."
    }
  ],
  "need_human": false,
  "lead_fields": {
    "product": "custom stainless steel bracket",
    "quantity": null,
    "country": "Germany",
    "email": null,
    "material": "stainless steel",
    "drawing_available": true
  },
  "follow_up_questions": [
    "Could you share the drawing or STEP file?",
    "What quantity do you need?",
    "Do you have surface treatment or tolerance requirements?"
  ],
  "trace_id": "trace-demo-001"
}
```

输出字段要求：

- `answer`：给访客的回答，优先英文。
- `language`：回答语言。
- `confidence`：0-1 之间。
- `sources`：回答依据，必须引用知识库 ID 或原文片段。
- `need_human`：是否需要人工跟进。
- `lead_fields`：从访客问题中抽取的客户线索。
- `follow_up_questions`：下一步应该问访客的问题。
- `trace_id`：本次请求的唯一追踪 ID。

## 5. 必须处理的情况

1. 知识库有明确答案：正常回答并引用证据。
2. 知识库没有相关信息：不能编造，必须 `need_human=true`。
3. 访客的问题太模糊：回答中要求补充信息。
4. 访客给了询盘线索：抽取产品、数量、国家、材料等字段。
5. LLM 或 mock LLM 返回非法 JSON：需要解析、修复、重试或降级。
6. 输入为空：返回明确错误，不要崩溃。

## 6. 日志要求

必须记录日志文件，例如 `logs/app.log` 或 `logs/traces.jsonl`。

每次请求至少记录：

- `trace_id`
- 原始输入
- 检索到的知识库片段
- LLM 原始输出或 mock 输出
- 最终 JSON 输出
- 错误信息
- 是否触发降级

## 7. 测试要求

请使用 `tests/test_cases.json` 中的测试问题。

至少提供：

- 5 条测试输入。
- 每条测试的输出结果。
- README 中说明如何运行测试。

可以是自动化测试，也可以是命令行运行截图/日志，但必须能复现。

## 8. 提交内容

请提交 GitHub 仓库或 zip 包，至少包含：

```text
README.md
.env.example
requirements.txt / package.json
app.py / src/
knowledge/
tests/
logs/ 或运行后可生成 logs/
```

README 必须写清楚：

1. 如何安装依赖。
2. 如何启动。
3. 如何运行测试。
4. 是否使用真实 LLM；如果使用，如何切换 mock 模式。
5. 你用了哪些 AI coding 工具。
6. 哪些代码/设计是你自己完成或修改的。
7. 当前项目的已知限制。

## 9. 加分项

- 支持多轮对话中的线索累积。
- 支持中英文问题。
- 支持把高价值询盘输出成 lead JSON。
- 支持简单后台页面。
- 有清晰的错误码。
- 有单元测试。

## 10. 重要提醒

不要只做一个聊天页面。我们会重点看代码是否能跑、回答是否有知识库证据、JSON 是否稳定、失败情况是否处理。

