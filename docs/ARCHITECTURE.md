# LogFusion-Agent 架构（依据代码，非 README 推断）

> 规模：`src/agent` 12 个模块 2454 行；`tests` 11 个文件 1466 行 / **125 个用例**；`frontend/agent_app.py` 171 行。
> 本文所有结论均可在对应文件行内核对。

## 1. 模块清单

| 模块 | 行数 | 职责 | 关键符号 |
|---|---:|---|---|
| `engine.py` | 748 | 控制回路：预算、循环、降级、闸门、结论生成、结果序列化 | `InvestigationAgent.run()`、`InvestigationResult`、`grounded_findings()`、`_pattern_findings()`、`is_empty_observation()` |
| `tools.py` | 383 | 只读工具集与工具契约 | `InvestigationTools`、`TOOL_SCHEMAS`（7 个）、`ToolArgumentError`、`failure_clusters()`、`OBSERVATION_CHAR_LIMIT=6000` |
| `planner.py` | 250 | 决策：规则剧本与 LLM 规划器，同一接口 | `RulePlanner`、`LLMPlanner.from_env()`、`build_messages()`、`system_prompt()` |
| `rag_index.py` | 210 | 案例索引构建与检索（TF-IDF / MiniLM / RRF） | `TfidfCaseRetriever`、`MiniLMRetriever`、`MiniLMOnnxEncoder`、`HybridCaseRetriever`、`normalize_query()` |
| `context.py` | 176 | 上下文层：三层记忆 + 可插拔策略 | `ContextPolicy`、`project_observation()`、`fold_observation()`、`build_ledger()` |
| `judgment.py` | 145 | 综合研判与引用校验 | `LLMJudgment.synthesize()`、`validate_judgment()`、`JudgmentValidationError` |
| `adapters.py` | 133 | 懒加载上游检测器与检索器 | `upstream_detector()`、`upstream_retriever()`、`minilm/tfidf/hybrid_case_retriever()` |
| `events.py` | 131 | 日志解析成事件对象 | `EventStore.from_bytes()/from_path()`、`LogEvent`、`parse_time()` |
| `__main__.py` | 120 | CLI 入口与 demo 套件 | `main()`、`run_suite()` |
| `profiles.py` | 115 | 日志方言层 | `LogProfile`、`SSH_AUTH`、`AUTH_GENERIC`、`get_profile()` |
| `demo.py` | 37 | 无密钥的模拟研判 | `SimulatedJudgment` |
| `__init__.py` | 6 | 包导出 | — |

## 2. 运行时调用链（`InvestigationAgent.run(goal)`）

1. `self.tools.reset()`；清空 planner / reviewer 的 token 计数。
2. **计划**：`planner.plan(goal)` → 写 `trace[0]`（`stage="plan"`，2–4 条假设）。规则规划器返回固定剧本假设。
3. **循环**（`for step in range(1, max_steps+1)`）：
   - 预算判定 → 是否进入收尾（`wrap_up`）→ 是否强制结束轮（`final`）
   - `planner.choose(goal, trace, wrap_up, final)` → 得到 `(name, arguments)`，其中 `rationale` 被剥离并记入 trace
   - 参数校验（schema 范围 + `inspect.signature().bind()`）→ `tools.call(name, arguments)`
   - 写入 trace（含错误类型）→ 空结果熔断 / 重复调用 / 簇后必查提示（`stage="hint"`）
   - `update_hypothesis` 会同步改 `plan[i]["status"]`
4. **终局审计**：未走 `planner_finished` 且闸门从未触发时，用 `_coverage_gaps(trace, plan)` 再评估一次，缺口写 `limitations`。
5. **结论**：`grounded_findings(self.tools)` —— 纯规则，从 `tools.evidence` 推导，模型无法写入。
6. **研判（可选）**：若有 reviewer 且状态为完成/部分完成 → 自动补一次 `retrieve_cases`（用 `profile.completion_query`）→ `reviewer.synthesize(...)` → `validate_judgment` 校验结构与引用 ID，失败带反馈修正一次。
7. **输出**：`InvestigationResult.to_dict() / to_markdown() / save()`。

## 3. 关键边界（容易讲错的地方）

- **工具是 7 个**：`detect_anomalies`、`aggregate_events`、`search_logs`、`get_event_context`、`update_hypothesis`、`retrieve_cases`、`build_timeline`。`finish_investigation` 是第 8 个 schema，但它是终止信号，不返回数据。
- **规划器不是一个独立服务**，是 `planner.py` 里两个类（`RulePlanner` / `LLMPlanner`）实现同一 `choose()` 接口；`plan()` 阶段可选，只有 `supports_plan` 为真才调用。
- **上游检测器不是工具层的硬依赖**：`adapters.upstream_detector()` 返回一个闭包，由入口注入 `InvestigationTools(detector=...)`；缺失时 `detect_anomalies` 退化为 `rule_signals`（规则候选信号），调查仍可完成。
- **证据与结论不在一个模块**：证据是 `EventStore` + `tools.evidence`（只读字典）；结论是 `engine.grounded_findings()` 模块级函数；研判是 `judgment.LLMJudgment`。三层不可混谈。
- **闸门与引用校验读 trace 和工具层状态，不读发给模型的消息**。所以 `context.py` 的压缩不会放宽“引用必须真查过”。
- **上下文层与方言层是后加的两层**，不在 `choose()` 里：`ContextPolicy` 决定这轮看到多少历史，`LogProfile` 决定用哪套词汇与话术。

## 4. 外部依赖

| 依赖 | 位置 | 缺失时行为 |
|---|---|---|
| 三视图检测器 + XGBoost 融合 | 父仓 `models/`（`xgboost_fusion.joblib` 等） | `upstream_detector()` 抛 `FileNotFoundError`；`--with-detector` 时调查失败，不带则用规则候选 |
| 案例索引 | `data/vectors/rag_attack_cases{,_tfidf,_minilm}.npz` | 逐级回退：MiniLM → TF-IDF → 上游哈希；全缺时 `retrieve_cases` 返回空并注明“不影响证据调查” |
| MiniLM ONNX | `rag_attack_cases_minilm.json` 里的 `model_dir`（外部路径） | 回退 TF-IDF |

## 5. 数据流

```
原文日志 → EventStore（event_id/时间/主机/IP/账号/类型）
   ├─ detect_anomalies：Drain3 → 50 条滑窗 → 三视图 → XGBoost → risk_score 排序 → 窗口锚点
   ├─ aggregate_events：按 (ip,user,host) 5 分钟 5 次聚簇
   ├─ search_logs / get_event_context：按实体与时间窗取原文（后者只接受已观察事件）
   └─ retrieve_cases：67 条案例（解释层，不进 evidence）
→ grounded_findings：规则推结论 → InvestigationResult（json + md）
```
