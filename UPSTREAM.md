# Upstream provenance

Repository: https://github.com/kingofbuilding/LogFusion-LLM
Branch: public-upload
Commit: 4c3a05b81cacacf5629b5677dab9e6f5a6e6d8c8

Source imported from the GitHub branch archive; original MIT license retained.

The public-upload archive omitted src/models because its broad models/ ignore rule also matched source directories. Required BiLSTM/IsolationForest model and trainer sources were recovered from the original local Git HEAD; the DeepLog trainer was recovered from the original local project.

## 本地训练产物（迁移自 log_analysis_system_complete）

公开仓库不含权重。为跑通评测 A/D 组，以下文件从本地前身工程 `D:\毕业设计\log_analysis_system_complete` 复制而来，不进入 Git：

| 文件 | 来源 | 作用 |
|---|---|---|
| `models/xgboost/xgboost_fusion.joblib` | 前身工程 `models/xgboost/` | 三视图融合分类器（100 棵树，hist） |
| `models/isolation_forest/iforest_model.joblib` | 前身工程 `models/isolation_forest/` | 统计视图 |
| `models/bilstm/best_model.pth` | 前身工程 `models/bilstm/` | 时序视图（Bi-LSTM + Attention） |
| `data/vectors/rag_attack_cases.npz` | 前身工程 `data/vectors/` | 67 条案例的向量索引（256 维） |

注意事项：

- 前身工程配置同样为 `force_hash_fallback: true`、`embedding_dim: 384`（运行时截断为 256），因此融合模型是在**哈希回退语义特征**上训练的；本仓库不要切换到 sentence-transformers，否则特征分布与训练时不一致。
- 迁移的索引与当前配置 `similarity_threshold: 0.7`、`raw_score_threshold: 0.65` 不匹配：哈希嵌入下查询与案例的最高余弦相似度约 0.14，检索结果为空。这不是索引损坏，而是嵌入方式本身的限制。
- Bi-LSTM 检查点以 `weights_only=False` 回退加载时会出现安全警告；仅加载来自本地可信来源的权重。

迁移后 `detect_anomalies` 返回真实模型分数（`upstream_three_view_xgboost`），评测 A 组与 D 组据此运行，详见 `docs/EVAL_REPORT.md`。
