# Agent 评测

## 运行 Router 模块评测

```powershell
uv run python -m eval.cli --suite eval/suites/router.yaml
```

此命令只运行 Router 相关用例。每条用例的重复次数由 `router.yaml` 配置，默认结果写入
`.data/eval/router_module.jsonl`。

CLI 会报告全部试验的通过率、各用例平均通过率，以及 `pass^k`（所有重复试验都通过的用例比例）。
同时会逐条显示用例的通过次数、通过率和 `pass^k` 结果。失败的试验会显示 trace ID，便于在
Platform 的 Trace 查看器中检查运行过程。

Router 用例集覆盖正向和反向路由场景，包括意图不明确的请求、业务字段解释、隐含的数据查询意图，
以及缺少筛选条件的查询。发现新的实际路由错误或尚未覆盖的边界情况时，应补充对应 Task。

## 运行整体回归评测

```powershell
uv run python -m eval.cli --suite eval/suites/regression.yaml
```

整体回归 Suite 通过引用各模块 Suite 组合评测，不需要重复维护 Task 清单。目前只有 Router 模块
具备可运行的 Suite，因此整体回归暂时只包含 Router。新增其他模块评测后，在 `suites:` 下添加引用即可。
整体回归 Suite 配置总体验收门槛，各模块 Suite 配置自己的重复策略。合并后的结果默认写入
`.data/eval/full_regression.jsonl`。

每个 Trial 会记录 SDK trace ID、Router 首次 handoff 的目标，以及 Router 完成的 handoff 次数。
模型调用需要配置 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`；配置 `OPENAI_TRACING_API_KEY` 后，运行轨迹会
上传到 OpenAI Platform。Runner 不会重复上传对话记录，也不会为这个确定性路由检查调用 LLM grader。

## Router 评分器

本地 `expected_handoff_target` grader 会将 Task 中的 `expected.handoff_target` 与 Router 首次实际
handoff 的 `HandoffOutputItem.target_agent.name` 比较。`exactly_one_router_handoff` grader 检查 Router
是否恰好发起一次已完成的 handoff。没有 handoff 时，这两项检查都会失败。Trial 记录的 trace ID 可用于在
Platform Trace 查看器中定位对应运行。

## E2E 样例

`datasets/e2e/customs_awb_exists.yaml` 定义了一个用于存在性查询的合成只读 SQLite fixture，其中的表名和字段名
只是示例，并非真实业务结构。当前尚未实现 E2E Runner、数据库执行器、安全评分器，以及样例引用的 Platform
回答评分器。该文件用于记录预期的 Task、环境和结果约定，尚未加入可运行的 Router Suite。
