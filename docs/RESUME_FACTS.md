# RESUME_FACTS — 简历每个数字的出处与口径

> 用途：面试前速查。每个数字对应「哪个文件、哪次运行、什么口径」。  
> 生成于 2026-10-22，对应简历第 8 版（`D:\文件\实习\简历_修订.docx`，仓库 HEAD `476fbc6`）。

## 项目一 LogFusion-Agent

| 简历上的数字                        | 出处                                                                                                                                                                                                                     | 面试口径                                                                                                                                                          |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 三子集平均 F1 0.91                 | `log_analysis_system_complete/.claude/worktrees/agent-a06760da/outputs/reports/stat_parts_fusion_eval_20260417.csv`，实验组 `fusion`、模型 `xgboost_fusion_saved_model`：harrison 0.9480 / santos 0.9180 / fox 0.8520，均值 0.906 | AIT-LDS 三个子集，train 24k / test 6k 固定切分，窗口 50 行，阈值在验证集上选                                                                                                        |
| 50 条滑窗                        | 父仓 `frontend/runtime.py` `seq_len=50`                                                                                                                                                                                  | 一个窗口 = 50 行日志，检测器输出窗口级分数                                                                                                                                      |
| 7 个只读工具                       | `src/agent/tools.py` `TOOL_SCHEMAS`（7 项）+ 第 8 个 `finish_investigation` 只发终止信号不计                                                                                                                                        | 6 个纯读 + 1 个改内部假设状态；对外部世界无写操作                                                                                                                                  |
| 16 步预算 / 2–4 条假设 / 每轮 1 个工具   | `run_eval.py PER_GROUP_BUDGET`；`planner.py` `[:4]` 截断、`calls[0]`；`tool_choice="required"`                                                                                                                              | 4 = 16 步 ÷ 每假设 3–4 步；单工具是因为下一步取决于这一步的结果                                                                                                                       |
| event_id 不在证据表即拒绝发布           | `src/agent/judgment.py validate_judgment()`                                                                                                                                                                            | 模型综合研判里每个引用都比对 `tools.evidence`，失败退回修正一次                                                                                                                      |
| 3 条用例中 2 条被退回重查               | 最近一次 3 条 LLM 评测：`gate_unresolved` ×2 + `planner_finished` ×1（余额耗尽前最后一批）                                                                                                                                                | 闸门平均 0.7 次/次的来源：2/3 ≈ 0.67                                                                                                                                    |
| 观察 10 KB → 876 字符             | `detect_anomalies`：检测器 30 条分数直接返回曾 ~10 KB；改为 top-N 窗口跨度 + 6k 裁剪后 876 字符                                                                                                                                                | 评测报告 3.2 节 C1                                                                                                                                                 |
| 6000 字符                       | `tools.py OBSERVATION_CHAR_LIMIT`                                                                                                                                                                                      | 单次观察硬上限                                                                                                                                                       |
| 44 条轨迹 token 降 13.6%          | `benchmarks/results/context_budget_replay.json`：44 条 / 378 次调用，full 961,692 → fold 830,534；≥10 步 −16.0%，最长 16 步 −22.1%                                                                                                 | 离线回放（不调 API）；字符数精确、token 为校准估算（误差 4%），**引比例别引绝对值**                                                                                                            |
| 57 条案例（内置 48 + 自动 9，清洗掉 10 条） | `scripts/prune_case_base.py`：语义密度（`<*>`≥2 淘汰）、主流量基线（count≥5000 淘汰）、跨库去重；备份 `.bak-20261022`                                                                                                                             | 清洗后攻击模板候选命中 13.9%（清洗前 20.9%）——**命中率衡量的是分布重叠不是质量**；清洗的验证是返回内容可解释（root 失败登录 → CASE-SEC-013），评价指标需相关性标注，未做                                                       |
| RRF k=10，权重 1:6               | `src/agent/rag_index.py` `reciprocal_rank_fusion` / `HybridCaseRetriever(weights=(1.0, 6.0))`                                                                                                                          | 按排名融合（分数不可比）；1:6 因为词法弱，等权 type@1 只有 0.538                                                                                                                     |
| 攻击模板候选命中率 21%                 | **2026-10-22 修正**：原"549 模板 91% 低于阈值"口径错误——查询集 79% 是正常流量模板，基率不匹配。用 harrison 行级标注（`data/raw/harrison/labels/`）筛出 115 条攻击模板重测：候选 20.9%（非攻击模板 7.0%，区分力存在但弱：0.348 vs 0.315，强命中 5.2%）                                        | 有效结论 = 区分力弱 + top-1 塌缩（13 案例/最热 58%）+ **案例库质量问题：19 条自动案例中 8 条为 `<*>` 零语义模板，AUTO-0001/0002 的 template_count 高达 71300/44223（主流 dnsmasq 模板因攻击者 DNS 活动被标注而整条入库）** |
| 42 条 7 类用例                    | `benchmarks/cases/manifest.json`：8+6+6+6+5+6+5 = 42，**合成**（生成器自述 synthetic）                                                                                                                                            | 7 类覆盖阳性和阴性；**前 21 条 = 顺序截断**，缺良性重试等阴性对照                                                                                                                       |
| 12 条盲区用例                      | `benchmarks/cases_hard/`，`generate_hard_cases.py` 4 类构造器：喷洒 / 低速 / 撞库 / 跨主机                                                                                                                                            | 规则召回 0 是**设计使然**（生成器断言不形成 5-in-5 簇）                                                                                                                           |
| 五组对照                          | `benchmarks/run_eval.py GROUPS = (rule, simulated, llm, upstream, agent+upstream)`                                                                                                                                     | 各组结论层相同，只差证据来源                                                                                                                                                |
| 完成率 43% → 95%                 | `docs/EVAL_REPORT.md` 3.2：C0（12 步，无参数范围）→ C1（16 步 + schema）                                                                                                                                                            | **混杂项**：步数预算 12→16 同时改，不能全归 schema；单次运行、前 21 条                                                                                                                |
| 盲区规则召回 0 → Agent 100%         | EVAL_REPORT 失效集（12 条，130k）                                                                                                                                                                                             | 0 是设计结果；证明的是"盲区存在 + Agent 能覆盖"，**不是**"Agent 比规则强 100%"                                                                                                        |
| 接入检测器无增量                      | EVAL_REPORT D 组 vs C 组：召回打平、精度 0.44→0.35、token +22%                                                                                                                                                                    | 负结果；窗口级分数帮不到事件级取证，且热区饱和（6 窗并列 0.9659）                                                                                                                         |
| 125 个测试                       | `pytest -q`：125 passed                                                                                                                                                                                                 | fake client / rule planner，不调 API                                                                                                                             |
| 2 MB 真实多源日志                   | harrison 四源各切 512 KB = 1.53 MB / 11,022 事件，0.28 s 加载，24,351 token 跑完                                                                                                                                                   | 只验证**链路**与**假设生成**；无标注，测不了结论对错                                                                                                                                |

## 项目二 越狱评测框架

| 简历上的数字                          | 出处       | 面试口径                                      |
| ------------------------------- | -------- | ----------------------------------------- |
| 8 模型 / 2100 条提示 / 16800 次调用     | 毕设论文实验章节 | 个人只负责 Prompt 生成组件；评测执行是团队                 |
| 组合攻击 GPT-4 成功率 19.61%（单类 5.30%） | 同上       | 19.61 / 5.30 ≈ 3.7 倍                      |
| 较基线 Jailbreaker 11.92% 提升 64.5% | 同上       | (19.61−11.92)/11.92 ≈ 64.5%               |
| 三要素 / 7 类场景 / 24 条非法问题          | 生成器设计    | 模板扩增用 GPT-4 同义改写（temperature=0.7），校验占位符位置 |

## 三个"不能说"与三个"要说"

**不能说**：

- ❌ "向量 RAG 提升了效果"——哈希索引实测 0.14 低于阈值，MiniLM 在生产查询形态下反而垫底
- ❌ "Agent 比规则强"——盲区召回 0 是构造出来的
- ❌ "支持任意多源日志"——语义端只有认证类方言，其余归 other

**要说**：

- ✅ 0.91 是三子集平均，切分 24k/6k
- ✅ 43%→95% 是"schema + 步数预算"的合并效果
- ✅ 42 条是合成数据，且前 21 条缺阴性对照

## 回归已复现（2026-10-23，HEAD 6064ca6）

前 21 条标准用例（130k 同口径）：**完成率 1.00（完全 0.29）、结论正确率 1.00、证据召回 1.00**、平均 13.4 步 / 85,168 token（缓存命中 27%）。43%→95% 在当前代码成立（EVAL_REPORT 第 6 节）。

**真实日志切片 3/3 跑通**（AIT-LDS 混合日志，各 ~3,675 行，共 90.5k token ≈ 0.24 元）：其中 2 条的模型研判被引用校验**实际拦截**、降级为"只发规则发现"——拒绝发布机制在真实数据上被触发验证，而非只在测试里（EVAL_REPORT 第 7 节）。

**引用校验新增相关性层**：claim 的全部引用为 `other` 类型即拒绝发布（`claim_evidence_not_semantic`）；127 tests passed。

## 外部评审六问应答（2026-10-23 补，对应一份外部简历评估的六个击穿点）

### Q1 三子集 F1 0.91 怎么算的？滑窗是否泄漏？——**有代码级依据**

- 切分实现在 `log_analysis_system_complete/src/data_processing/data_loader.py:_prepare_ordered_pre_split`：**按行号顺序切**（`iloc[:train_end]`），不是随机划分；metadata 记录 `train_row_range/val_row_range/test_row_range`。
- 每个切分**独立滑窗**：`_build_split_bundle` 记录 `global_start_indices = start_idx + row_offset`，val/test 的窗口只在自己区间内构建，**不存在跨 train/test 边界的窗口**。
- 阈值只在 val 上选：`truncated_protocol.py` 明确 `"test_used_for_selection": False`；harrison 还做了 trunc_ratio=0.80 截断。
- P/R/F1 明细：stat_parts_fusion_eval CSV（harrison P 0.9256 / R 0.9715 / F1 0.9480）。
- **仍要承认的**：三子集来自同一框架的三个场景，泛化到全新环境的验证没做；子集内攻击基率不同，宏平均与微平均会有差异（简历写的是宏平均）。

### Q2 盲区 100% 召回是否用例太容易？——**口径已防，置信区间是新弹药**

- 简历口径已是"规则召回 0、Agent 100%"且盲区为构造——0 是设计使然，不构成对比优势。
- 新增弹药：12 次全成功的 Clopper–Pearson 95% 置信下限 ≈ 73.5%——被追问时主动给出，反而加分。
- "召回"定义：证据召回（关键事件的 event_id 被查过），不是攻击类型分类正确率。

### Q3 完成率 43%→95% 是否只靠放宽预算？——**简历已自带诚实归因**

- 简历括号写明"工具契约收紧 + 步数预算放宽"，混杂已承认。
- "完成"的口径：completed = 走完流程出报告且无闸门未决项；另有 verdict 正确率（与期望结论比对）作为结论层指标，两组指标分开。

### Q4 每轮 1 工具是不是真 Agent？——**有真实动态决策轨迹**

`outputs/investigations/INV-a629dd03638c`（15 步）：

- step 1 聚合验证 H1 → **step 2 换参数再聚合**（查"同 IP 对多账户"的喷洒形态）
- step 3 **基于 step1/2 得知的源 IP** 转查该 IP 的成功登录 → step 4 **因找到成功登录**跟进读上下文
- step 12 主动回查检测器确认没有遗漏其他窗口 → step 13 证据足够才 confirm H1  
  每一步的 `rationale` 都在 trace 里，可现场展示。模型返回多个工具调用时只取第一个（`calls[0]`），但**选哪个工具、传什么参数完全由模型根据观察决定**。

### Q5 RAG 21% 的价值？——**定位已收敛，评审建议与现行一致**

- 简历口径"只作解释参考、与证据分表存储、不参与事实判定"就是评审建议的写法。
- RRF 无准确率保证——同意；k=10 是业界常用值，1:6 是标注模板实验测得（等权 0.538 → 1:6 更优）。

### Q6 引用校验 ≠ 证据可靠？——**承认边界，部分有覆盖**

- 已覆盖：引用有效性（ID 在证据表）、证据完整性（闸门查后继登录）、不确定性表达（insufficient_evidence 判定 + limitations 披露）。
- 未覆盖：证据相关性、推理充分性无自动化校验——由规则函数的判定逻辑间接约束。**如实承认是边界**，与"规则出结论"的设计一致：结论层只有 3 种判定，宁缺毋滥。

## Ecom-DeepResearch 简历数字出处（2026-10-23 核实，全部有产物背书）

源码持久位置：`D:/毕业设计/deepsearch-agents`（从 WorkBuddy 会话目录迁移，二开已提交 `1cb2f18`，18 文件 +4,269 行）；产物在 `D:/WorkBuddyOutput/deepsearch-agents/deliverables/`。

| 简历断言 | 证据 |
|---|---|
| 49 次跨工具调度 / 361s | `run3.json`：`duration_sec=361.2`、`tools_called=49`、`assistants_called=4` |
| 检索 33 次压降至 ≤5 | 测试报告 21 行：提示词约束"完全失效"，单轮实际触发 33 次 Tavily 检索；618 复盘那次"检索恰好 5 次"；假模型回归"连续 8 次、实际执行 5 次" |
| ToolCallLimitMiddleware 自研 | `app/agent/search_limit.py`（90 行，AgentMiddleware 协议）：thread_id 分桶计数（ContextVar）、`before_agent` 任务级重置、超限返回中文指路 ToolMessage + monitor 联动；limit 支持 arg/env/default |
| 23 页 PDF | pypdf 实测 `618复盘报告.pdf` = 23 页 |
| 8+6 项回归 | `tools/run_checks.py`（8 项，8/8 通过，含假模型限流 e2e）+ `tools/run_failure_checks.py`（6 项失败场景，3 个当场抓到真实缺陷） |
| "GMV 与 SQL 完全一致" | 测试报告 4.1 对照表：6 项关键数字（SKU 6、库存 73,200、第一名 21,700、29.6%、65.0%、扩展 11 SKU/168,400）与 SQL 基准逐项 ✅；GMV 107,743 vs 日常 30,722（3.5 倍）写入回归 C2 |

**面试要点（唯一需防守处）**：`ToolCallLimitMiddleware` 类名与 LangChain 1.2 官方中间件**同名**。如被问"是不是 import 官方的"：实现是独立的（基于 `wrap_tool_call`/`awrap_tool_call` 协议自己写的拦截），且官方版没有 thread_id 分桶计数、任务级重置、中文指路 ToolMessage、monitor 联动这四点。

## 得物价格获取的穷举结论（2026-10-23，arb-scout 调研）

尝试过的 9 种方法及结果：
1. 得物 web 搜索（web.dewu.com）→ fetch failed（反爬）
2. 得物 H5 搜索/商品页（m.dewu.com）→ 200 但为 4KB JS 空壳，数据接口需 anti-content 签名
3. 识货 PC 详情页 SSR → 仅 SEO 元数据，"得物"只出现在宣传文案（`total:1` 渠道）
4. 识货 H5 → 同 PC
5. Next.js `_next/data` 数据路由 → 404
6. JS bundle 挖 API 端点 → 页面 0 个 chunk（加载方式不同），无线索
7. 识货 NEXT_DATA 渠道键（channel/platformList 等）→ 不存在，渠道在 CSR
8. App 抓包（anti-content 逆向）→ 未尝试：法律灰色 + 脆弱，明确排除
9. WebSearch 间接来源 → ✅ **有意外收获**：京东价 799.99（常卖价=历史最低）、识货社区晒单 700 元；但得物商品数据**完全不进搜索引擎**（只有官网落地页）

**最终结论：得物精确价格只能人工在得物 App 确认（Quote.platform="dewu", kind="manual"）。** 这是穷举后的边界，不是设计缺陷。系统已按此设计：得物价无 manual 确认 → `insufficient_evidence`，拒绝出利润。

**WebSearch 可作为参照系数据源**（事实支持的弱来源）：
- 京东价 799.99（常卖价=历史最低，`union-click` 搜索结果带慢慢买历史价格数据）
- 识货社区晒单 700 元（飞影 PLAID 3.0，`m.shihuo.cn/page/findCommunityDetail?id=6007414`）
- 参照系用途：判断"478 的群价有多罕见"——比京东便宜 40%，接近识货社区成交价
