# RESUME_FACTS — 简历每个数字的出处与口径

> 用途：面试前速查。每个数字对应「哪个文件、哪次运行、什么口径」。
> 生成于 2026-10-22，对应简历第 8 版（`D:\文件\实习\简历_修订.docx`，仓库 HEAD `476fbc6`）。

## 项目一 LogFusion-Agent

| 简历上的数字 | 出处 | 面试口径 |
|---|---|---|
| 三子集平均 F1 0.91 | `log_analysis_system_complete/.claude/worktrees/agent-a06760da/outputs/reports/stat_parts_fusion_eval_20260417.csv`，实验组 `fusion`、模型 `xgboost_fusion_saved_model`：harrison 0.9480 / santos 0.9180 / fox 0.8520，均值 0.906 | AIT-LDS 三个子集，train 24k / test 6k 固定切分，窗口 50 行，阈值在验证集上选 |
| 50 条滑窗 | 父仓 `frontend/runtime.py` `seq_len=50` | 一个窗口 = 50 行日志，检测器输出窗口级分数 |
| 7 个只读工具 | `src/agent/tools.py` `TOOL_SCHEMAS`（7 项）+ 第 8 个 `finish_investigation` 只发终止信号不计 | 6 个纯读 + 1 个改内部假设状态；对外部世界无写操作 |
| 16 步预算 / 2–4 条假设 / 每轮 1 个工具 | `run_eval.py PER_GROUP_BUDGET`；`planner.py` `[:4]` 截断、`calls[0]`；`tool_choice="required"` | 4 = 16 步 ÷ 每假设 3–4 步；单工具是因为下一步取决于这一步的结果 |
| event_id 不在证据表即拒绝发布 | `src/agent/judgment.py validate_judgment()` | 模型综合研判里每个引用都比对 `tools.evidence`，失败退回修正一次 |
| 3 条用例中 2 条被退回重查 | 最近一次 3 条 LLM 评测：`gate_unresolved` ×2 + `planner_finished` ×1（余额耗尽前最后一批） | 闸门平均 0.7 次/次的来源：2/3 ≈ 0.67 |
| 观察 10 KB → 876 字符 | `detect_anomalies`：检测器 30 条分数直接返回曾 ~10 KB；改为 top-N 窗口跨度 + 6k 裁剪后 876 字符 | 评测报告 3.2 节 C1 |
| 6000 字符 | `tools.py OBSERVATION_CHAR_LIMIT` | 单次观察硬上限 |
| 44 条轨迹 token 降 13.6% | `benchmarks/results/context_budget_replay.json`：44 条 / 378 次调用，full 961,692 → fold 830,534；≥10 步 −16.0%，最长 16 步 −22.1% | 离线回放（不调 API）；字符数精确、token 为校准估算（误差 4%），**引比例别引绝对值** |
| 57 条案例（内置 48 + 自动 9，清洗掉 10 条） | `scripts/prune_case_base.py`：语义密度（`<*>`≥2 淘汰）、主流量基线（count≥5000 淘汰）、跨库去重；备份 `.bak-20261022` | 清洗后攻击模板候选命中 13.9%（清洗前 20.9%）——**命中率衡量的是分布重叠不是质量**；清洗的验证是返回内容可解释（root 失败登录 → CASE-SEC-013），评价指标需相关性标注，未做 |
| RRF k=10，权重 1:6 | `src/agent/rag_index.py` `reciprocal_rank_fusion` / `HybridCaseRetriever(weights=(1.0, 6.0))` | 按排名融合（分数不可比）；1:6 因为词法弱，等权 type@1 只有 0.538 |
| 攻击模板候选命中率 21% | **2026-10-22 修正**：原"549 模板 91% 低于阈值"口径错误——查询集 79% 是正常流量模板，基率不匹配。用 harrison 行级标注（`data/raw/harrison/labels/`）筛出 115 条攻击模板重测：候选 20.9%（非攻击模板 7.0%，区分力存在但弱：0.348 vs 0.315，强命中 5.2%）| 有效结论 = 区分力弱 + top-1 塌缩（13 案例/最热 58%）+ **案例库质量问题：19 条自动案例中 8 条为 `<*>` 零语义模板，AUTO-0001/0002 的 template_count 高达 71300/44223（主流 dnsmasq 模板因攻击者 DNS 活动被标注而整条入库）** |
| 42 条 7 类用例 | `benchmarks/cases/manifest.json`：8+6+6+6+5+6+5 = 42，**合成**（生成器自述 synthetic） | 7 类覆盖阳性和阴性；**前 21 条 = 顺序截断**，缺良性重试等阴性对照 |
| 12 条盲区用例 | `benchmarks/cases_hard/`，`generate_hard_cases.py` 4 类构造器：喷洒 / 低速 / 撞库 / 跨主机 | 规则召回 0 是**设计使然**（生成器断言不形成 5-in-5 簇） |
| 五组对照 | `benchmarks/run_eval.py GROUPS = (rule, simulated, llm, upstream, agent+upstream)` | 各组结论层相同，只差证据来源 |
| 完成率 43% → 95% | `docs/EVAL_REPORT.md` 3.2：C0（12 步，无参数范围）→ C1（16 步 + schema） | **混杂项**：步数预算 12→16 同时改，不能全归 schema；单次运行、前 21 条 |
| 盲区规则召回 0 → Agent 100% | EVAL_REPORT 失效集（12 条，130k） | 0 是设计结果；证明的是"盲区存在 + Agent 能覆盖"，**不是**"Agent 比规则强 100%" |
| 接入检测器无增量 | EVAL_REPORT D 组 vs C 组：召回打平、精度 0.44→0.35、token +22% | 负结果；窗口级分数帮不到事件级取证，且热区饱和（6 窗并列 0.9659） |
| 125 个测试 | `pytest -q`：125 passed | fake client / rule planner，不调 API |
| 2 MB 真实多源日志 | harrison 四源各切 512 KB = 1.53 MB / 11,022 事件，0.28 s 加载，24,351 token 跑完 | 只验证**链路**与**假设生成**；无标注，测不了结论对错 |

## 项目二 越狱评测框架

| 简历上的数字 | 出处 | 面试口径 |
|---|---|---|
| 8 模型 / 2100 条提示 / 16800 次调用 | 毕设论文实验章节 | 个人只负责 Prompt 生成组件；评测执行是团队 |
| 组合攻击 GPT-4 成功率 19.61%（单类 5.30%） | 同上 | 19.61 / 5.30 ≈ 3.7 倍 |
| 较基线 Jailbreaker 11.92% 提升 64.5% | 同上 | (19.61−11.92)/11.92 ≈ 64.5% |
| 三要素 / 7 类场景 / 24 条非法问题 | 生成器设计 | 模板扩增用 GPT-4 同义改写（temperature=0.7），校验占位符位置 |

## 三个"不能说"与三个"要说"

**不能说**：
- ❌ "向量 RAG 提升了效果"——哈希索引实测 0.14 低于阈值，MiniLM 在生产查询形态下反而垫底
- ❌ "Agent 比规则强"——盲区召回 0 是构造出来的
- ❌ "支持任意多源日志"——语义端只有认证类方言，其余归 other

**要说**：
- ✅ 0.91 是三子集平均，切分 24k/6k
- ✅ 43%→95% 是"schema + 步数预算"的合并效果
- ✅ 42 条是合成数据，且前 21 条缺阴性对照

## 待复现（当前代码 vs 简历数字）

今天改了三处（`2498ad2` plan 提示词 / `2649046` 截断修复 / `476fbc6` 侦察阶段），简历上的 43%→95% 是改动**之前**测的。**约 2.6 元**可跑前 21 条回归确认；未跑前，被追问时如实说"这批数字是重构前测的，重构后的回归还没跑"。
