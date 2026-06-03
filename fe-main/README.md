# fe-main — 外贸客服 Agent 控制台前端

基于 **React 18 + TypeScript + Vite** 的企业级控制台界面，把后端 Agent 的能力可视化：
对话、知识库证据引用、置信度、`need_human` 状态、累积询盘线索、错误码、追问引导。

## 界面构成（三栏布局）

| 区域 | 内容 |
|------|------|
| 顶部栏 | 品牌标识 + 实时健康状态（LLM 模式 Mock/DeepSeek、知识库条数、在线状态，来自 `/health`） |
| 左栏 | 会话设置（session_id / 国家 / 邮箱）、新会话、刷新线索、示例问题一键发送 |
| 中栏 | 对话气泡：访客 / Agent / **错误码气泡**；每条 Agent 回答带 `need_human`/语言/`trace_id` 徽章；追问可点击直接发送 |
| 右栏 | **本轮分析**（置信度环形仪表 + 状态徽章）、**知识库证据 Sources**（按 C/P/F 着色的 ID + 原文）、**询盘线索 Lead**（多轮累积、完整度进度条、一键导出 JSON） |

需求项与界面的对应：`answer`→气泡正文；`confidence`→环形仪表；`sources`→证据卡片；
`need_human`→红/绿徽章；`lead_fields`→线索表（累积）；`follow_up_questions`→可点击 chips；
`trace_id`→气泡徽章；错误码（如空输入 `E1001`）→错误气泡。

## 两种运行方式

### 方式 A：随后端一起跑（推荐，单端口，同源）

后端会自动挂载本前端的构建产物，无需第二个服务、无跨域问题。

```bash
# 1. 构建前端
cd fe-main
npm install
npm run build          # 产物输出到 fe-main/dist

# 2. 启动后端（项目根目录），浏览器打开 http://127.0.0.1:8000/
cd ..
uvicorn src.server:app --port 8000
```

### 方式 B：前端独立热更新开发

```bash
# 终端 1：后端
uvicorn src.server:app --port 8000

# 终端 2：前端开发服务器（Vite 代理 /chat /health /lead 到 8000）
cd fe-main
npm run dev           # 打开 http://127.0.0.1:5181
```

> 开发端口在 [`vite.config.ts`](vite.config.ts) 中配置（默认 5181，`strictPort`）。
> 如端口被占用，改该值即可。

## 目录

```text
fe-main/
├── index.html
├── vite.config.ts        # 端口 + /chat /health /lead 代理
├── src/
│   ├── main.tsx
│   ├── App.tsx           # 页面编排与状态
│   ├── api.ts            # 类型契约 + fetch 封装
│   ├── components.tsx    # 置信度仪表 / 证据 / 线索 / 徽章 / 卡片
│   └── styles.css        # 企业级设计系统（CSS 变量、卡片、徽章、动效）
└── ...
```

技术选择：未引入重型 UI 框架，用一套自定义 CSS 设计系统（统一的色板、圆角、阴影、卡片与
徽章规范）实现企业级观感，依赖最小、构建最快。
