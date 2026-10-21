# 阶段 0：真实 LLM 基线运行记录

运行时间：2026-10-21T16:17:02Z

## 配置

- 输入：`data/demo/ssh_investigation.jsonl`（15 条合成 SSH 日志）
- 模型：本地 `.env` 配置的 `deepseek-flash`
- 模式：`llm_tool_calling`，每次最多 12 个调查轮次，累计预算 100000 tokens，时间预算 120 秒。
- 记录：只保存工具名、阶段、错误类型、运行状态、token 数和证据/案例数量；没有保存 API Key。

## 5 次摘要

| 次数 | 状态 | 停止原因 | 工具轮数 | Token | 关键观察 |
|---:|---|---|---:|---:|---|
| 1 | limited | `repeated_tool_call` | 1 | 2275 | aggregate_events；工具错误 1 次 |
| 2 | completed | `planner_finished` | 12 | 79170 | aggregate_events, detect_anomalies, aggregate_events, search_logs, get_event_context, search_logs, search_logs, search_logs, get_event_context, retrieve_cases, build_timeline, synthesize_judgment；工具错误 1 次 |
| 3 | completed | `planner_finished` | 11 | 60291 | aggregate_events, detect_anomalies, aggregate_events, aggregate_events, search_logs, get_event_context, search_logs, search_logs, retrieve_cases, build_timeline, synthesize_judgment；工具错误 2 次 |
| 4 | completed | `planner_finished` | 10 | 57140 | aggregate_events, detect_anomalies, aggregate_events, search_logs, get_event_context, search_logs, search_logs, retrieve_cases, build_timeline, synthesize_judgment；工具错误 1 次 |
| 5 | completed | `planner_finished` | 12 | 71702 | aggregate_events, detect_anomalies, aggregate_events, search_logs, search_logs, get_event_context, get_event_context, search_logs, search_logs, retrieve_cases, build_timeline, synthesize_judgment；工具错误 2 次 |

## 观察

- 4/5 次到达综合研判；第 1 次因 `repeated_tool_call` 提前结束。
- 完整运行平均 67076 tokens，中位数 71702；平均工具轨迹 11.2 步。
- 模型会传入超出白名单范围的 `window_minutes`、`max_groups` 等参数；工具层拒绝后调查可继续，但产生额外 token 成本。
- 工具顺序不稳定：有时先调用检测，有时先聚合；有时重复查询相同实体或上下文。
- 作为阶段 1 的评测重点：结论 verdict、关键证据召回、跨账号/跨主机误关联、重复/无效调用率、token 成本和完成率。

## 限制

- 只有一个合成 SSH 场景，不能证明 Agent 泛化到 Web 或生产日志。
- 5 次运行不能代表模型长期稳定性；完整评测应固定用例、重复运行并报告失败样本。
- 本记录来自真实模型调用，但不作为模型质量结论；阶段 1 使用独立标注用例评估。
