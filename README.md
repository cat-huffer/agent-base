# agent-base

## 项目介绍

## 核心功能简介

## 快速开始

### 1. 安装依赖

项目使用 Python 3.12 和 uv 管理依赖：

```powershell
uv sync
```

### 2. 配置环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写 `APP_ENV`、`DEFAULT_MODEL_PROFILE` 和 `OPENAI_API_KEY`（DeepSeek Key）。默认 profile 为 `default`，`OPENAI_BASE_URL` 指向 DeepSeek 的兼容接口。应用加载 `app.config` 时会将 `.env` 放入进程环境，Agents SDK 随后自行读取这些环境变量；`.env` 仅用于本地开发，不要提交到版本库。

后端启动时配置 Loguru 控制台日志；`LOG_LEVEL` 默认为 `INFO`，需要更多诊断信息时可在 `.env` 中设为 `DEBUG` 并重启服务。

### 3. 配置模型与路由

模型和路由配置位于 `src/agent/models/profiles/`：

- `models.yaml`：定义模型 profile、模型名称和模型参数。
- `router.yaml`：将业务路由映射到对应的模型 profile。

当前 `chat` 路由映射到 `default` profile。DeepSeek 已支持 Responses API，后端沿用 Agents SDK 的默认 API 模式。

修改模型或路由配置后，重启后端服务即可生效。

### 4. 启动后端

在项目根目录执行（应用从该目录读取 `.env`，并以该目录解析相对数据路径）：

```powershell
make dev-backend
```

如果 Windows 尚未安装 `make`，可直接执行等价命令：

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 访问服务

- API 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

`POST /chat` 接收 `session_id` 和 `message`，返回 `message` 与 `trace_id`。同一 `session_id` 的后续请求会通过 SDK AsyncSQLiteSession 读取此前的对话；换一个 ID 则开始新会话。会话数据库路径由 `SESSION_DB_PATH` 配置，默认是启动时工作目录下的 `.data/sessions.sqlite3`；相对路径以启动时工作目录为基准。

`POST /chat/stream` 接收相同请求体，返回 `text/event-stream`。事件依次包含 `started`（`trace_id`）、零个或多个 `message.delta`（`delta`），最后是 `completed`（完整 `message`）或 `error`。前端可用 `fetch` 读取 POST 响应流；`POST /chat` 保留给需要完整结果的调用方。同一进程内，同一 `session_id` 的请求会依次执行；不同会话可并行。

每次运行的 SDK trace metadata 包含会话 ID、Agent、模型 profile、Prompt ID 与版本、运行环境。若要导出到 OpenAI Traces，可在 `.env` 中另填 `OPENAI_TRACING_API_KEY`（OpenAI Key）；未配置时本地对话可运行，但不会导出 trace。追踪不包含对话正文。

```json
{"session_id": "abc123", "message": "我叫张三"}
```

## 技术栈概览

## 目录结构说明
