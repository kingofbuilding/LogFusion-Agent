# Agent MVP 设计与评估规划

核心侧重点是告警后的自主调查与证据关联。

## 已实现结构

- events.py：允许字段投影、时间归一化、实体提取、稳定事件 ID。
- tools.py：六种只读工具、证据收集、查询边界与案例分离。
- planner.py：离线剧本与 LLM 工具调用两种规划器。
- engine.py：执行预算、循环控制、已查证据关联与结果导出。
- adapters.py：原检测与向量 RAG 的延迟加载适配。
- frontend/agent_app.py：独立及嵌入式调查工作台。

LLM 决定查询路径，规则发现受 SSH 证据规则约束；综合研判由单独 LLM 阶段生成。当前不是通用自治 SOC。

## 评测（阶段 1 已执行）

已实现 `benchmarks/`：42 条标注 SSH 用例（固定种子、7 类关联/干扰场景）、规则/模拟/LLM/上游一次性/Agent+上游 五组评测、按类别的结论正确率与证据召回统计。首次结果、失败样本诊断与限制见 [EVAL_REPORT.md](EVAL_REPORT.md)。

上游检测器、Bi-LSTM 与 RAG 索引已从前身工程 `log_analysis_system_complete` 迁移（见 [UPSTREAM.md](../UPSTREAM.md)），A 组与 D 组因此可运行。迁移的向量索引以哈希回退嵌入构建，阈值下检索为空，D 组的差异只来自检测器；恢复语义检索需重新安装 sentence-transformers 并重建索引，同时要接受检测器语义视图的特征分布变化。

## 2026-10-22 收尾与降级

工具阶段只使用 `max_steps - 2` 步和约 2/3 的 token，剩余预算显式保留给案例检索与综合研判。这样每次调查都以“发现 + 证据 + 研判 + 报告”结束，而不是撞到预算就 `limited`。

三个降级路径：

1. 工具预算用尽 → `status=completed`、`stop_reason=evidence_budget`，研判基于已查证据，并写入“提前收束”的限制。
2. 重复工具调用 → 把“这次调用已执行过”作为观察回灌，允许换工具；连续两次重复才收束。
3. 连续工具错误或研判连续被拒 → 仍完成调查：前者保留已查证据，后者只发布规则发现，二者都在报告中标注原因。

预算不足以保证收尾（例如总量小到连一次研判都放不下）时，仍回退到 `limited` 并写明 `token_budget`，不伪装成成功。

## 2026-10-22 计划、理由与假设状态

调查开始前先做一次规划调用（`plan()`），得到 2–4 条可验证假设，编号 `H1..H4`，初始状态 `open`。规划失败不阻塞调查，只是没有计划区。

工具循环中：

- 每次调用必须带一句 `rationale`（“为什么现在查这个”），引擎把它从参数里取出、写入轨迹，不传给工具；
- 工具 `update_hypothesis(hypothesis_id, status, note)` 允许模型把假设标为 `confirmed` / `refuted`；引擎据此更新 `result.plan` 并记录 `updated_at_step`；
- 未知假设 ID 只回一条错误提示，不修改计划。

产物：`investigation.json` 的 `plan` 字段与 `trace[].rationale`；`report.md` 顶部有“调查计划与假设”一节，工具记录里带理由；Streamlit 工作台在页签上方展示计划与状态，轨迹页显示每步理由。

规则剧本同样走这套结构：固定三条假设，并在聚合、成功登录、上下文三个阶段各自更新，便于离线演示“假设 → 动作 → 更新”的完整形态。

## 2026-10-22 完整性闸门

模型申请 `finish_investigation` 时不是立即结束，而是先做覆盖检查（最多退回 2 次）：

1. 已观察到的每个失败簇，是否用 `search_logs(event_type=auth_success)` 查过同实体、同主机的后继登录；
2. 与失败簇同账号、同主机且发生在簇结束后 15 分钟内的成功登录，是否用 `get_event_context` 核对过上下文；
3. 计划里的假设是否全部停在 `open`（若是，提示用 `update_hypothesis` 给出结论）；
4. 一条证据都没看就申请结束，直接退回。

缺项以 `completeness_gate` 轨迹条目返回（`control` 字段，不算工具错误），包含具体缺口文本；模型可据此补齐或说明无法补齐的原因。非收尾阶段最多退回 2 次；进入收尾后不再退回（已无预算补查），改为拒绝结束并按部分完成收口。退回次数与缺口写进 `limitations`。

## 2026-10-22 收尾终端化

实测问题是：模型拿到预算后几乎从不主动调用 `finish_investigation`，闸门因此从未被真正触发（3 条 × 1 次运行，`gate_triggers` 全为 0）。只调阈值无效——固定比例（如工具预算的 90%）可能被单次调用一步跨过，收尾模式在同一轮里被置位又跳过。

现在的做法：

1. 收尾起点按**观测到的单轮成本**动态预留（`1.5 × 已用 token / 已完成动作数`，不超过工具预算的一半），保证收尾阶段至少能拿到一轮。
2. 收尾是终端阶段：`WRAP_UP_TURNS = 2`，第一轮用于 `update_hypothesis` 收束假设，第二轮为**强制结束轮**——只暴露 `finish_investigation` 并锁定 `tool_choice`。若供应商忽略强制选择，引擎记录 `ignored_tool_call` 并按结束处理。
3. 收尾阶段允许动用一半的完成预留 token 关门；超过则该轮结束，仍保留研判所需预算。
4. 闸门在收尾阶段的结束请求上照常评估：有缺口时拒绝一次并直接收口，`stop_reason=gate_unresolved`，缺口写进 `limitations`；若模型连强制结束轮都未产生结束请求，则在循环后做**终局审计**（`terminal: true`），同样计入 `gate_triggers` 并披露，`stop_reason=wrap_up_terminal`。

评测新增 `gate_terminal_refusals`（终局被闸门拒绝的次数），与 `gate_triggers` 分开统计，避免把“审计发现缺口”和“模型被退回后补齐”混为一谈。


## 2026-10-22 上下文管理：三层记忆与控制回路的耦合

上下文管理此前不是一层架构，而是 `choose()` 里的一段循环——每轮按完整 trace 重建 messages，第 n 步的输入包含前 n-1 步的全部观察。后果是成本随步数平方增长，而引擎对此一无所知：它按 `tokens_used` 判预算，却不知道这笔钱一半花在重复运送同一批观察上。实测拆解（19 条 trace / 16 次调用 / 88,615 token）：固定开销（system 1,417 + 8 个 schema 4,574 字符 ≈ 1,536/次）占 29%，历史重发占 70%，模型输出仅 1.4%。

现在把它做成独立的一层（`src/agent/context.py`），并明确了它与控制回路的三个耦合点。

### 三层记忆

```
指令层    system prompt + 8 个工具 schema          恒定 ~1,536 token/次
─────────────────────────────────────────────────────────────────
工作记忆  最近 4 条 trace，原文回放                 受 project_observation 约束
          （events ≤20 行、raw ≤600 字符）
─────────────────────────────────────────────────────────────────
情景台账  更早的轮次                                 fold：保形定位投影
                                                    compact：一段文字台账
```

- **fold（默认）**：保留 assistant/tool 消息形状，`events` 仍是列表，只留 `event_id/timestamp/event_type/host/user/src_ip`，最多 6 行，丢弃 `raw/source/line`。小于 420 字符的观察不折叠——摘要有自己的 note，折小的会变大。
- **compact（`AGENT_HISTORY_MODE=compact`，默认关）**：把旧轮次压成一条 user 消息的台账，历史成本从平方降为常数，代价是丢掉旧的 tool 消息结构。
- **full（`AGENT_HISTORY_MODE=full`）**：优化前行为，保留用于离线 A/B 回放。

`ContextPolicy` 是一个 frozen dataclass，planner 只调用 `policy.build(goal, trace, system)`，不再知道压缩策略的存在；`layout()` 用来报告三层各有多少条目。策略选择走环境变量，非法值退回 `fold` 而不是让一次调查失败。

### 与控制回路的三个耦合点

1. **收尾触发**：原先是"预算用了多少"这一个信号；现在上下文体积本身也是信号——空结果熔断（连续 2 次空集注入 `EmptyResultHint`，第 3 次直接进收尾）让"这一轮有没有产出"参与终止判断。
2. **预算口径**：`tokens_used` 仍是名义值（含缓存命中），预算因此保守；`tokens_cached` 单独累计 `prompt_cache_hit_tokens`，让成本口径可解释而不改变守口逻辑。
3. **不变量**：**上下文可压缩，trace 不可压缩**。完整性闸门的 `_coverage_gaps()` 与研判的 `validate_judgment()` 读 trace 与工具层状态，因此压缩永远不会把"没查过"变成"查过"，也不会让引用校验放宽。

### 度量

`benchmarks/measure_context.py` 离线回放 `outputs/investigations/*/investigation.json`，不需要 API key，用同一批决策对比三种策略的 payload。44 条轨迹 / 378 次调用：fold 平均降 13.6%（≥10 步轨迹 16.0%，最长轨迹 22.1%），compact ≥10 步降 33.7%、16 步轨迹降 49.5%；空结果占 20/378 次（5.3%），10 条轨迹受影响，单条最多 7 次。compact 的行为等价性尚未用真实模型验证，故默认关闭。



## 2026-10-22 日志方言层：LogProfile

此前“哪种日志”这件事散落在 6 个文件、31 处字面量里：事件分类 if 链（`events.py`）、失败/成功过滤与覆盖检查（`engine.py`、`tools.py`）、规则剧本与系统提示（`planner.py`）、完成阶段固定查询 `"SSH brute force ..."`、结论话术。结果是：换一种日志就要改引擎，而引擎本身对日志格式没有任何依赖。

现在把它收拢成一层（`src/agent/profiles.py`）：

| 字段 | 作用 |
|---|---|
| `rules` | 有序谓词表，决定一行日志归类为 failure / success / escalation / other（`all_of` / `any_of` / `regex` 可嵌套） |
| `failure_type` / `success_type` / `escalation_types` | 引擎、工具层、规则剧本引用的语义名，不再写字面量 |
| `completion_query` | 完成阶段补检索案例用的查询 |
| `label` | 报告与限制文案里的域名称 |
| `user_patterns` | 从原文抽账号的正则 |

引擎按 `store.profile` 取词汇；`InvestigationAgent` 构造时把 planner 的 profile 同步成日志的 profile，避免“提示词说 SSH、日志是 RADIUS”的静默错配。CLI 新增 `--profile`，未知值回退默认。

已实现两个 profile：`ssh_auth`（默认，行为与改造前逐字节一致）与 `auth_generic`（RADIUS/PAM 风格，不含 `sshd` 字样）。后者用 7 条合成日志端到端跑通：规则剧本产出 2 条结论、引用可解析、限制文案自动变成“通用认证日志”。7 个新测试覆盖方言分类、跨方言不误分类、非 SSH 端到端、提示词渲染与回退。

**边界必须说清**：profile 换的是**日志方言**（词汇、话术、完成查询），不是**安全语义**。结论规则（5 分钟 5 次簇、喷洒、撞库、低速爆破）与案例库仍假设“失败爆发 → 同实体成功 → 后继活动”这条认证叙事；Web 访问日志、进程行为需要新的结论规则，尚未实现。把这条写进文档，比假装“通用日志分析”更经得起追问。

## 迭代顺序

1. 更完整的 SSH 解析、时间补全、多失败窗口与分页查询。
2. 会话/进程 ID 和跨文件关联，减少同账号并发误归因。
3. 持久化状态、取消恢复、预算细化与真实服务兼容验证。
4. 人工标注事件级评估，随后扩展 Web 等调查场景。

## 2026-10-21 综合研判链路

Agent 的 completion 阶段自动补齐案例检索，再调用 LLMJudgment。模型采用工具 `publish_judgment` 提交结构化观察、推断、建议与不确定性，结构和引用检查后才发布。无效引用最多修正一次，错误或预算停止都不伪装为成功。

判断只能引用本次研判上下文中的事件 ID；案例永远不能替代原始日志。引用校验不做自然语言事实蕴含判断，该能力仍是后续研究方向。

CLI 和 Streamlit 使用相同核心。原 LLM 模式自动启用综合研判；--llm-judge 支持规则调查加真实模型研判；--mode simulated 用明确标注的本地模拟模型演示全部阶段，不是实际模型评测。
