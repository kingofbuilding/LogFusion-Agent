# README_public_benchmarks

本模块为当前项目新增的公开基准补充实验流水线，仅覆盖 **HDFS** 与 **BGL**，目标是尽量对齐 LogBERT 论文中的公开基准数据处理方式，但**只训练与评估本文自己的模型**。

## 目录结构

- `benchmarks/public_logs/`
  - `preprocess_hdfs.py`
  - `preprocess_bgl.py`
  - `dataset_utils.py`
  - `split_utils.py`
- `benchmarks/configs/`
  - `hdfs.yaml`
  - `bgl.yaml`
- `benchmarks/models/`
  - `temporal_public.py`
  - `semantic_public.py`
  - `statistical_public.py`
  - `fusion_public.py`
- `benchmarks/runners/`
  - `run_hdfs_public.py`
  - `run_bgl_public.py`
  - `run_public_benchmarks.py`
- `benchmarks/reports/`
  - `make_public_tables.py`

## 协议说明

### HDFS
- 使用日志解析后的 log key / template 序列
- 按 `BlockId` 构建序列
- 同一 `BlockId` 不跨 train/val/test
- 训练集只保留正常序列
- val/test 同时保留正常与异常序列
- 序列中只要包含异常日志，则该序列标记为异常

### BGL
- 使用日志解析后的 log key / template 序列
- 先按 `event_ts` 升序排序，再使用时间滑窗构建序列
- 默认窗口大小 5 分钟
- 默认步长 1 分钟
- 按时间顺序切分 train/val/test
- 训练集只保留正常窗口
- val/test 同时保留正常与异常窗口
- 窗口中只要包含异常日志，则该窗口标记为异常
- 当前 `semantic_public_*` 的语义输入模式为 `template_sequence_text`

## 模型
- `temporal_public`
- `temporal_public_bgl_sequence`
- `temporal_public_bgl_deeplog`
- `semantic_public_template`
- `semantic_public_raw`
- `semantic_public_hash`
- `statistical_public`
- `fusion_bgl_stat_semraw`
- `fusion_public_mean`
- `fusion_public_weighted`
- `fusion_public_mean_bgl_deeplog`
- `fusion_public_weighted_bgl_deeplog`
- `fusion_bgl_stat_temp_deeplog`

其中：
- `temporal_public` 现已改为 **normal-only next-event prediction**，使用前缀序列预测下一个 log key，并以 `top-k miss ratio` 作为正式序列异常分数。
- BGL 额外提供一个仅用于对照的 `temporal_public_bgl_sequence`，使用 sequence-level `longest miss burst ratio` 聚合，不进入正式 fusion。
- BGL 额外提供一个更接近 DeepLog score 定义的 `temporal_public_bgl_deeplog`，使用 `1 - P(true_next_event)` 的 sequence mean 作为连续异常分数；它用于与当前仓库口径对照，不等于完整复现论文版 DeepLog。
- `semantic_public_template` 必须走真实 template embedding 路径；若实际运行中回退到 hash，则该行保留但状态标为 `invalid_due_to_hash_fallback`，不得解释为正式 template 结果。
- `semantic_public_raw` 使用窗口内 raw event/message text，经噪声字段清洗后送入同一 embedding backend，用于验证 BGL 的主要瓶颈是否来自 template-level 语义表达不足。
- `semantic_public_hash` 作为当前可运行的 hash 语义异常分数分支保留。
- `statistical_public` 只使用通用窗口统计特征：序列长度、unique template 数、高频模板比例、稀有模板比例、熵、重复率、模板转移数。
- 对于 strict normal-only 的 HDFS，本轮不再使用监督式 `XGBoost` 做 `fusion_public`，而改用合法的 score fusion：`fusion_public_mean` 与 `fusion_public_weighted`。
- BGL 额外补充 `fusion_public_mean_bgl_deeplog` 与 `fusion_public_weighted_bgl_deeplog`，用于检验把 DeepLog-style temporal score 接入 fusion 后是否优于当前 temporal 口径。
- DeepLog / LogBERT 不在本仓库中复现，其结果仅作为 literature baseline 写入最终表格，`Source=reported_in_LogBERT`。

## 运行命令

### HDFS
```bash
python benchmarks/runners/run_hdfs_public.py
```

### BGL
```bash
python benchmarks/runners/run_bgl_public.py
```

如需快速验证，可先在 `benchmarks/configs/bgl.yaml` 中临时设置：
- `benchmarks.public_logs.max_train_samples`
- `benchmarks.public_logs.max_val_samples`
- `benchmarks.public_logs.max_test_samples`

这样会在保持原有时间顺序切分的前提下，仅截取每个 split 的前一部分样本做对照验证。

### HDFS + BGL 汇总
```bash
python benchmarks/runners/run_public_benchmarks.py
python benchmarks/reports/make_public_tables.py
```

## 输出位置

### 中间产物
- `outputs/reports/public_benchmarks/intermediate/hdfs_parsed.csv`
- `outputs/reports/public_benchmarks/intermediate/hdfs_sequences.csv`
- `outputs/reports/public_benchmarks/intermediate/bgl_parsed.csv`
- `outputs/reports/public_benchmarks/intermediate/bgl_sequences.csv`

### 结果文件
- `outputs/reports/public_benchmarks/public_benchmark_hdfs_*.csv`
- `outputs/reports/public_benchmarks/public_benchmark_bgl_*.csv`
- `outputs/reports/public_benchmarks/public_benchmark_all_*.csv`
- 对应 `*.json`

### 表格文件
- `reports/public_benchmark_hdfs_table.md`
- `reports/public_benchmark_bgl_table.md`
- `reports/public_benchmark_summary_table.md`
- `reports/public_benchmark_summary_table.csv`

## 结果表字段
最终表格字段为：
- `Dataset`
- `Model`
- `Precision`
- `Recall`
- `F1`
- `AUC`
- `PR-AUC`
- `Status`
- `Notes`
- `Source`

BGL 对应的 JSON 结果还会额外保存协议字段：
- `sort_strategy`
- `split_strategy`
- `train_filter`
- `window_minutes`
- `stride_minutes`
- `semantic_input_mode`
- `temporal_score_mode`
- `temporal_comparison_score_mode`
- `temporal_deeplog_score_mode`

此外还会额外生成：
- `bgl_semantic_raw_audit.json`
  - 用于记录 `semantic_public_raw` 的输入模式、阈值来源以及相对 template semantic / statistical_public 的诊断性对照结果

其中：
- `Status` 可能取值：
  - `valid`
  - `invalid_due_to_hash_fallback`
  - `invalid_due_to_single_class_supervised_training`
  - `skipped_due_to_single_class_train`
  - `reported_baseline`
- `Source` 可能取值：
  - `reproduced_in_this_work`
  - `reported_in_LogBERT`

## Alignment with LogBERT protocol

本模块的目标不是 **100% 复现 LogBERT**，而是对其**公开可见的 benchmark protocol 尽量对齐**，并在当前仓库中只运行本文自己的模型。

### 严格对齐的部分
- **数据集选择一致**：使用 `HDFS` 与 `BGL`
- **序列构造方式一致**：
  - `HDFS` 使用 `BlockId` 构造序列
  - `BGL` 使用 **5 分钟窗口 + 1 分钟步长** 构造序列
- **训练协议一致**：
  - train 只保留正常样本
  - val / test 同时保留正常与异常样本
- **评估重点一致**：
  - 重点输出 `Precision / Recall / F1`
  - 同时补充 `AUC / PR-AUC` 作为本文额外统计

### 合理实现的部分
以下部分不追求与 LogBERT 完全逐行一致，而采用当前仓库内可复用、可解释、可运行的合理实现：
- **日志解析实现**：使用当前仓库的 `DrainParser` 与现有模板抽取流程，而非强行绑定某一特定 Drain 版本
- **模板细节与文本规整方式**：模板归一化、掩码规则和文本拼接方式基于本仓库现有实现
- **模型内部超参数**：训练轮数、GRU/IsolationForest 等参数采用当前仓库可复现实验配置
- **语义表示实现**：`semantic_public_template` 与 `semantic_public_hash` 复用本仓库已有语义编码与 hash fallback 机制；当 template 路径实际回退到 hash 时，结果会被显式标为无效
- **融合实现**：对 strict normal-only 的 HDFS，使用基于 anomaly score 的 mean / weighted fusion，而不是监督式 XGBoostFusion

### 结论口径
因此，本目录下的结果应表述为：
- **protocol-aligned public benchmark experiments**
- **aligned with publicly visible LogBERT benchmark settings where possible**
- **not a full reimplementation of LogBERT**

## Alignment with LogBERT on HDFS

### 严格对齐项
- 使用 `HDFS` 公开数据集
- 日志先解析为 log key / template 序列
- 以 `BlockId` 作为序列构造单位
- 同一 `BlockId` 只能出现在 train / val / test 之一
- train 只保留正常序列
- val / test 同时保留正常与异常序列
- 序列级标签规则为：序列中只要包含异常日志，则该序列标记为异常
- 阈值来源固定为 `val`，不允许在 `test` 上搜索阈值

### 合理实现项
- parser / Drain 版本采用当前仓库现有实现
- 模板归一化、掩码与文本拼接复用当前仓库代码
- temporal / semantic / statistical / fusion 的模型细节采用当前仓库可复现实现，而非复现 LogBERT 本体
- 额外补充 `AUC / PR-AUC` 作为本文辅助统计

### Leakage audit status
- 当前 HDFS 结果必须同时通过以下检查才视为有效：
  - BlockId 两两交集为 0
  - threshold source = val
  - fusion 输入特征不存在 label / target / anomaly 等可疑标签列
  - 标签打乱实验后结果不能仍然异常偏高
- 审计结果保存于：
  - `outputs/reports/public_benchmarks/hdfs/hdfs_split_audit.json`
  - `outputs/reports/public_benchmarks/hdfs/hdfs_feature_audit.json`
- 若任一审计失败，则当前 HDFS 实验结果应视为**未通过 leakage audit**，不应继续作为“高分结果”提交。

## 注意事项
- 不修改主实验默认入口与默认配置。
- 新逻辑集中在 `benchmarks/` 下。
- Thunderbird 当前仅保留可扩展位置，本轮未实现。
