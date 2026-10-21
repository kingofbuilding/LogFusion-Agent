# 阶段 1 评测报告：SSH 调查 Agent

运行日期：2026-10-22（UTC+8）
代码基线：`33f9717` 加本轮未提交改动（评测框架、训练产物迁移、上游工程同步过来的工具 schema 修复）
模型：`.env` 中配置的 `deepseek-flash`，`temperature=0`

## 1. 目的

1. LLM 自主调查相对固定 SSH 剧本，是否查到了不同的证据、改变了结论？
2. 接入上游已训练检测器后，证据选择与结论是否更好？代价是多少？
3. 干扰项（异账号、异主机、窗口外成功登录）是否被错误关联？

## 2. 评测集

`benchmarks/cases/`，由 `python -m benchmarks.generate_cases` 以固定种子 `20260115` 生成，共 42 条，每条 49–72 条日志。

| 类别 | 数量 | 期望结论 | 设计意图 |
|---|---:|---|---|
| `bruteforce_then_success` | 8 | `correlated_success` | 6–8 次失败后 15 分钟内同实体成功登录，阳性用例 |
| `bruteforce_no_success` | 6 | `no_correlated_success` | 达到失败阈值但无后续成功登录 |
| `success_other_account` | 6 | `no_correlated_success` | 同 IP、同主机、另一账号成功登录 |
| `success_other_host` | 6 | `no_correlated_success` | 同 IP、同账号、另一主机成功登录 |
| `success_outside_window` | 5 | `no_correlated_success` | 同实体成功登录发生在失败窗口后 18–40 分钟 |
| `benign_retries` | 6 | `insufficient_evidence` | 2 分钟内 3 次输错后成功，低于 5 次阈值 |
| `multi_cluster` | 5 | `correlated_success` | 两个失败簇并存，仅第一个有后续成功 |

- **标签隔离**：期望只在 `ssh-XXX.json` 中，工具只能读到 `ssh-XXX.jsonl`；测试断言日志行只有 `timestamp/host/message` 三个字段。
- **生成器自检**：写盘后用与 Agent 相同的 `failure_clusters` 反解失败簇，必须与注入的簇完全一致。
- **实体隔离**：场景源地址使用文档保留段，背景噪声统一 `192.0.2.0/24`。
- **无上游数据交集**：用例全部为本项目合成，不存在与上游训练集重复的事件；代价是噪声真实性弱于真实日志。

## 3. 分组

| 组 | 实现 | 运行次数 | 预算（步/秒/token） |
|---|---|---:|---|
| B 规则剧本 | `RulePlanner` + 证据规则结论 | 42 | 16 / 60 / 24000 |
| S 模拟研判 | B + 本地确定性研判，跑通检索→研判→引用校验 | 42 | 16 / 60 / 24000 |
| A 上游一次性 | 迁移的融合检测器，展开最高风险窗口 + 一次案例检索 | 42 | 2 次调用 |
| C0 纯 LLM（修复前） | `deepseek-flash` 工具调用 + 研判，旧 schema | 21 | 12 / 120 / 100000 |
| C1 纯 LLM（修复后） | 同上，工具 schema 带参数范围与可读错误 | 21 | 16 / 120 / 100000 |
| D Agent+上游 | C1 的工具集加入检测器与向量 RAG | 21 | 16 / 120 / 100000 |

三组共用同一结论层 `grounded_findings`：结论由已查证据按显式规则生成，模型只决定查什么。**因此 verdict 差异只能来自“查到了哪些证据”，这正是本评测想衡量的东西。**

### 3.1 迁移的上游训练产物

| 文件 | 来源 | 作用 |
|---|---|---|
| `models/xgboost/xgboost_fusion.joblib` | `log_analysis_system_complete` | 三视图融合分类器 |
| `models/isolation_forest/iforest_model.joblib` | 同上 | 统计视图 |
| `models/bilstm/best_model.pth` | 同上 | 时序视图 |
| `data/vectors/rag_attack_cases.npz` | 同上 | 67 条案例向量索引（256 维） |

检测器按配置的 `temporal_sequence_length=50` 打分：一条日志至少要有 50 条窗口才能出分，因此 `ssh-033`、`ssh-036`（49 条）在 A 组返回 `detector_unavailable`。

### 3.2 C0 与 C1 的差别不只是 schema

C0 跑在修复前：工具 schema 只声明 `integer` 类型，`max_groups` 上限 10 写在代码里，模型只能试错；C0 中 100% 的运行至少出现一次工具错误，2 例连续 3 次错误被终止。修复后 schema 带 `minimum/maximum`，越界错误会以可读文本回灌给规划器（`retry_guidance`），C1 的工具错误率降到 0.24。

C1 同时把步数预算从 12 提到 16，因此 **C0→C1 的提升是“schema 修复 + 预算放宽”的合并效果，不能全部归因于 schema**。两者都使用同一 21 条子集。

### 3.3 向量索引的实际情况

迁移的索引以哈希回退嵌入构建（`force_hash_fallback: true`，维度 256），查询与案例的最高余弦相似度约 **0.14**，低于 `raw_score_threshold: 0.65` 与 `similarity_threshold: 0.7`，因此 `retrieve_cases` 在该索引下返回空。**D 组的差异来自检测器，不来自语义检索。** 这不是索引损坏，而是嵌入方式的限制；要恢复语义检索需安装 sentence-transformers 并用 MiniLM 重建索引，但检测器是在哈希特征上训练的，切换后其特征分布会漂移。

## 4. 指标

| 指标 | 定义 |
|---|---|
| 结论正确率 | 由 findings 推出的 verdict 与 `expected.verdict` 一致 |
| 证据召回 | `must_find_event_ids` 被实际查询到的比例 |
| 证据精度 | 已查证据中属于标注事件的比例（暴露窗口级证据“召回高、精度低”） |
| 关联召回 | `must_link_event_ids` 出现在“失败后成功登录”发现中的比例 |
| 误关联 | `must_not_link_event_ids` 被任何发现引用 |
| 跨簇误配 | 成功登录与另一失败簇同时出现在同一条发现中 |
| 步数 / token | 工具步数（不含综合研判）与总 token |
| 完成率 | `status == completed` |
| 工具报错率 | 至少一次工具调用失败 |

## 5. 结果

### 5.1 总览

| 组 | 运行 | 结论正确率 | 证据召回 | 证据精度 | 误关联 | 平均步数 | 平均 token | 完成率 | 工具报错率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B 规则剧本 | 42 | 1.00 | 1.00 | 0.26 | 0 | 5.3 | 0 | 1.00 | 0 |
| S 模拟研判 | 42 | 1.00 | 1.00 | 0.26 | 0 | 5.3 | 0 | 1.00 | 0 |
| A 上游一次性 | 42 | 1.00 | 1.00 | **0.14** | 0 | 2.0 | 0 | 0.95 | 0.05 |
| C0 纯 LLM（修复前） | 21 | 0.86 | 0.83 | — | 0 | 10.1 | 71073 | **0.43** | **1.00** |
| C1 纯 LLM（修复后） | 21 | **1.00** | 1.00 | — | 0 | 9.6 | 73206 | 0.81 | 0.24 |
| D Agent+上游 | 21 | 1.00 | 1.00 | 0.18 | 0 | 11.8 | 88768 | 0.52 | 0.24 |

### 5.2 A 组分类别

| 类别 | 结论正确率 | 证据召回 | 证据精度 | 平均步数 |
|---|---:|---:|---:|---:|
| `bruteforce_then_success` | 1.00 | 1.00 | 0.17 | 2.0 |
| `bruteforce_no_success` | 1.00 | 1.00 | 0.15 | 2.0 |
| `success_other_account` | 1.00 | 1.00 | 0.11 | 2.0 |
| `success_other_host` | 1.00 | 1.00 | 0.13 | 2.0 |
| `success_outside_window` | 1.00 | 1.00 | 0.12 | 2.0 |
| `benign_retries` | 1.00 | — | — | 1.7 |
| `multi_cluster` | 1.00 | 1.00 | 0.16 | 2.0 |

### 5.3 C 与 D 的停止原因

| 停止原因 | C0（12 步） | C1（16 步） | D（16 步） |
|---|---:|---:|---:|
| `planner_finished` | 9 | 17 | 11 |
| `max_steps` | 8 | 0 | 0 |
| `token_budget` | 1 | 2 | **9** |
| `judgment_rejected` | 0 | 2 | 1 |
| `repeated_tool_call` | 1 | 0 | 0 |
| `tool_error_limit` | 2 | 0 | 0 |

## 6. 发现

1. **schema 修复是本轮最大的单点收益**：C0 中 100% 的运行至少一次工具错误，根因是模型反复传 `max_groups=20`（上限 10）而 schema 没写范围；修复后错误率降到 0.24，完成率由 0.43 升到 0.81。诊断细节：`aggregate_events(window_minutes=60, min_failures=3, max_groups=20)` 连续失败两次，第三次去掉 `max_groups` 才成功。
2. **上游检测器确实能圈到正确的区域，但不能定位到事件**：A 组结论正确率与召回都是 1.00，代价是证据精度只有 0.14（每次约 50 条窗口日志中只有约 7–8 条是标注事件），且需要人工从窗口里找。这正是“窗口级检测 + 事件级调查”应当分工的地方。
3. **A 组的高分不能当作检测能力证明**：结论仍由同一套规则从窗口证据推出，而窗口几乎覆盖整个日志，因此 1.00 是证据粒度过粗的结果，不是模型判别力的结果。
4. **把检测器接进 Agent 反而降低完成率**：D 组 9/21 撞 `token_budget`（C1 只有 2 次），因为 `detect_anomalies` 一次返回 30 条分数加窗口跨度，观察体量远大于 `aggregate_events`；平均 token 从 73k 升到 89k，完成率从 0.81 降到 0.52，结论正确率没有提升。
5. **向量 RAG 在本机不可用**：索引相似度上限 0.14，阈值 0.65/0.7 下检索为空，D 组的 RAG 分支没有产生任何案例。
6. **误关联与跨簇误配在所有组均为 0**：异账号、异主机、窗口外成功登录从未被错误关联，两个失败簇也没有被混配。这由证据层规则保证，不是模型能力，但它支持“结论不交给模型生成”的设计选择。
7. **`temperature=0` 不是确定性的**：复跑诊断时 `ssh-016` 正常完成、`ssh-010` 换成另一种停止原因，轨迹与首次评测不同；单次运行只能当样本。

## 7. 限制（必须与结论一起引用）

- **标签与规则同源**：期望结论按同一套 5 次/5 分钟/15 分钟规则构造，B 组接近 100% 是构造使然，存在天花板效应。verdict 正确率衡量的是**管线一致性**，不是真实入侵检测能力。
- **A 组结论层是复用规则**：上游原生输出是风险窗口与报告，不是本报告的三种 verdict；A 组的映射只为可比性。
- **C0→C1 存在混杂**：schema 修复与步数放宽同时发生，无法分离贡献。
- **C/D 只跑 1 次、每类 3 条**：单模型、单温度，无法给出方差。
- **合成日志、单一场景**：没有 LogHub 真实噪声，没有 Web/sudo 场景。
- **向量索引不可用**（见 3.3），D 组不能回答“上游 RAG 是否仍有价值”。
- **引用校验只验证 ID**：通过校验不代表自然语言判断与证据语义一致。
- **C1 的 5 次 `JudgmentValidationError` 被记为停止原因**：研判被拒时保留规则发现，但该次运行计为未完成，完成率因此偏低。

## 8. 复现

```bash
python -m benchmarks.generate_cases --check       # 用例与生成器一致
python -m benchmarks.run_eval                     # B 组，42 条，离线
python -m benchmarks.run_eval --groups rule,simulated
python -m benchmarks.run_eval --groups upstream   # A 组，需要 models/ 与 data/vectors/
python -m benchmarks.run_eval --groups agent+upstream --limit 20
python -m benchmarks.run_eval --groups llm --repeats 3 --limit 20
```

本报告引用的结果文件：

| 组 | 文件 |
|---|---|
| B、S | `benchmarks/results/eval_rule_simulated_20261021T235121Z.json` |
| A | `benchmarks/results/eval_upstream_20261021T233851Z.json` |
| C0 | `benchmarks/results/eval_llm_20261021T164242Z.json` |
| C1 | `benchmarks/results/schema16/eval_llm_20261021T233038Z.json` |
| D | `benchmarks/results/eval_agent+upstream_20261021T234451Z.json` |

## 9. 下一步

1. 让 Agent 选择性使用检测器（例如只取窗口首尾或按实体聚合），避免一次 30 条分数撑爆上下文，目标是把 D 的完成率拉回 0.8 以上。
2. 同一 21 条上分别跑「12 步 + 新 schema」与「16 步 + 旧 schema」，把 C0→C1 的两个变量分离。
3. 用 MiniLM 重建 RAG 索引，并重新训练或至少重标定融合模型，否则检测器与索引的语义特征不一致。
4. 补到 42 条 × 3 次重复，报告均值与方差。
5. 阶段 3：注入样本，测结论篡改率与预算耗尽率（仓库已有 `benchmarks/run_injection.py` 与 `benchmarks/results/injection/`）。
