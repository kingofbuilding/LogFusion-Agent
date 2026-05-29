# 安全日志分析助手

## 项目简介

本项目面向毕业设计场景，目标是将日志异常检测、多视图融合、RAG 相似案例检索和大模型辅助研判整合为一条完整、可运行、可展示的安全日志分析链路。

当前版本的主流程为：

```text
日志读取
-> 预处理与 Drain 模板解析
-> 序列构建
-> 三视图风险评估
   -> 统计视图：Isolation Forest + 模板统计特征 + 原始日志安全统计代理特征
   -> 时序视图：Bi-LSTM + Attention
   -> 语义视图：蒸馏日志文本 + hash 表示
-> XGBoost 融合判定
-> 高危日志定位
-> RAG 相似案例检索
-> LLM 中文研判报告生成
-> Streamlit 前端展示
```

## 当前主线配置

当前仓库需要区分 **论文实验主线** 和 **前端默认运行口径** 两套含义：

### 1. 论文实验主线（最新重跑结果）

截至当前，论文实验链已经收口到以下主线：

- 协议 ID：`truncated_ordered_pre_split_v1`
- `split_mode`：`truncated_ordered_pre_split`
- 阈值来源：`val`
- `test_used_for_selection=false`
- 主实验数据：AIT-LDS v2 未筛选整子集
- 覆盖子集：`harrison / santos / fox`
- 基础窗口：`50`
- 时序视图窗口：`50`
- 统计视图窗口：`30`
- 当前 canonical 语义模式：`hash`
- 当前 canonical 主检测路线：`统计子分拆分 + XGBoost 融合`
- RAG 定位：检测后的相似案例检索与研判增强

与该主线直接对应的最新实验产物包括：

- `reports/final_thesis_package/semantic_context_window_truncated_report_20260420_092953.md`
- `reports/final_thesis_package/semantic_mode_compare_truncated_report_20260420_094815.md`
- `outputs/reports/protocol_compare_ordered_random_truncated_summary_20260420_144148.csv`
- `reports/final_thesis_package/thesis_experiment_tables_manifest_20260420.json`

### 2. 前端默认运行口径

前端当前默认仍以 `configs/config.yaml` 为准，主要用于演示和本地推理；目前已默认对齐到论文主线协议，但它仍表示“默认演示入口”，不等同于整套论文实验脚本重跑：

- 默认数据集：`harrison`
- 默认 `split_mode`：`truncated_ordered_pre_split`
- 默认基础窗口：`50`
- 默认时序窗口：`50`
- 默认统计窗口：`30`
- 默认语义模式：`hash`
- 默认语义上下文窗口：`1`
- 默认前端阈值：`0.68`
- 前端主检测模型：`ThreeViewScoringService + XGBoost 融合`

也就是说：**README 里的“实验主线”应以最新 truncated protocol 重跑结果为准；前端默认配置只是演示入口，不应再与论文实验主线混写。**

## 主要功能

### 1. 检测主链路
- 支持日志读取、模板解析、序列构建
- 支持统计视图、时序视图、语义视图三路打分
- 支持 XGBoost 融合输出最终风险分
- 支持 DeepLog 作为时序基线模型
- 支持 `Top-K / Recall@K` 排序能力评估

### 2. RAG 与研判增强
- 支持默认案例库加载与增量扩充
- 支持活动案例库重建与索引更新
- 支持 `Top-1 / Top-3 / Top-5 case hit` 评估
- 支持高危日志相似案例检索
- 支持基于检索结果的大模型中文研判报告

### 3. 前端展示
- 支持多格式日志上传
- 支持高危日志快速筛选与定位
- 支持三段式证据链展示：主判断、RAG 证据、原始证据
- 支持案例展示、深度问答、报告导出

### 4. 前端安全分类
当前前端已对常见安全日志模式做了规则细分，覆盖以下主要类别：

- 认证失败/暴力破解
- 账号探测/用户枚举
- 可疑成功登录
- 可疑会话建立
- Root 账户成功登录
- SSH 公钥登录异常
- 网站扫描/探测
- 后台入口探测
- 路径遍历/敏感文件探测
- SQL 注入
- XSS 注入
- 命令注入/远程执行
- 可疑文件上传/WebShell
- 审计提权痕迹
- sudo 特权执行
- 账户变更/权限变更
- 持久化任务变更
- 敏感文件篡改
- 反弹 Shell/远程控制
- 可疑下载执行
- FTP 可疑访问
- OpenVPN 远程接入
- OpenVPN 接入异常
- 数据库认证异常
- 系统资源耗尽/OOM
- 内核/服务崩溃
- 未授权访问
- 蜜罐命中/外部探测
- 其他可疑行为

## 目录结构

```text
.
|-- configs/
|   `-- config.yaml
|-- data/
|   |-- processed/
|   |-- rag/
|   |-- raw/
|   `-- vectors/
|-- frontend/
|   |-- app.py
|   |-- helpers.py
|   |-- panels.py
|   `-- runtime.py
|-- models/
|   |-- bilstm/
|   |-- deeplog/
|   |-- isolation_forest/
|   `-- xgboost/
|-- outputs/
|   `-- reports/
|-- reports/
|   `-- final_thesis_package/
|-- scripts/
|-- src/
|   |-- data_processing/
|   |-- feature_extraction/
|   |-- fusion/
|   |-- models/
|   |-- rag/
|   `-- utils/
|-- FUNCTION_UPDATE_LOG.md
|-- QUICKSTART.md
|-- README.md
`-- main.py
```

## 环境安装

建议使用 Python 3.10+。

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env.example` 只保留占位符。需要启用大模型中文研判时，请在本地 `.env` 中填写 DeepSeek、Qwen 或 OpenAI 等服务的 API Key；不使用 LLM 报告生成功能时可留空。请不要把 `.env` 或真实密钥提交到 GitHub。

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
AI_JUDGE_API_KEY=your_api_key_here
```

## GitHub 发布说明

本仓库公开版本只建议上传源码、配置模板、文档和少量安全示例数据。以下目录属于本地数据、模型或运行产物，默认不随 GitHub 仓库发布：

```text
data/raw/
data/processed/
data/vectors/
models/
outputs/
output/
reports/
.claude/
```

这些文件不会被删除，只是不进入 Git 跟踪范围。需要复现实验时，可按下方命令重新下载/解析数据、训练模型、构建 RAG 索引并生成输出结果。若需要公开展示实验结果，建议只保留脱敏后的摘要文档，不上传真实日志、模型权重、向量索引、论文个人材料或 API Key。

## 常用命令

### 解析日志
```bash
python main.py --parse
```

### 提取特征
```bash
python main.py --extract
```

### 训练模型
```bash
python main.py --train --train-mode all
```

### 评估视图与融合结果
```bash
python main.py --evaluate-views --eval-datasets harrison,santos,fox
```

### 构建活动 RAG 案例库
默认会按配置中的安全日志子集构建，不再走 `hdfs`。

```bash
python main.py --build-rag --rag-force
```

### 一键完成训练与 RAG 重建
```bash
python main.py --all --train-mode all --with-rag --rag-force
```

### 启动前端
```bash
python main.py --frontend
```

## 前端使用说明

推荐阅读顺序：

1. 上传日志文件
2. 设置风险阈值与筛选条件
3. 先看高危日志快速定位
4. 再看三段式证据链：主判断、RAG 证据、原始日志
5. 如有需要，再查看技术分析与自然语言报告

## 支持的上传格式

- `.log`
- `.txt`
- `.text`
- `.jsonl`
- `.json`
- `.csv`
- `.tsv`
- `.xlsx`
- `.xls`
- `.parquet`
- `.gz`
- `.zip`

## 关键配置说明

主要配置文件：`configs/config.yaml`

当前重要默认项包括：

- 默认数据集：`harrison`
- 默认 `split_mode`：`truncated_ordered_pre_split`
- 默认基础窗口：`50`
- 默认时序窗口：`50`
- 默认统计窗口：`30`
- 默认语义模式：`hash`
- 默认语义上下文窗口：`1`
- 默认 RAG 案例库增量数据集：`fox / harrison / santos`
- 默认前端阈值：`0.68`
- 默认 RAG 检索数：`top_k = 3`

如需复现实验主线，请不要直接依赖这里的前端默认项，而应以 `truncated_ordered_pre_split_v1` 对应的实验脚本与产物为准。

## 当前已知边界

- 统计视图已保留，但单独判别能力较弱，更适合作为辅助分支
- 语义视图默认采用蒸馏文本的 hash 表示，整体更像局部风险先验而非通用语义理解模块
- RAG 当前是中小规模案例增强库，不是通用大规模文档型 RAG
- RAG 相似度更适合作为排序参考，不应直接当作概率解释
- 前端安全分类规则已明显细化，但仍不是工业级全量规则库

## 相关文档

- 快速开始：[QUICKSTART.md](./QUICKSTART.md)
- 当前版本说明：`reports/final_thesis_package/release_note_current_version.md`
- 实验总收口方案：`reports/final_thesis_package/thesis_one_stop_plan.md`
- 第 3 章方法设计：`reports/final_thesis_package/chapter3_method_design.md`
- 第 4 章 RAG 与大模型研判增强：`reports/final_thesis_package/chapter4_rag_llm_analysis.md`
- 第 5 章实验分析：`reports/final_thesis_package/chapter5_experiment_analysis.md`
- 答辩问答：`reports/final_thesis_package/defense_qa.md`
- 功能修改记录：[FUNCTION_UPDATE_LOG.md](./FUNCTION_UPDATE_LOG.md)
