# 快速开始

## 1. 安装依赖

建议使用 Python 3.10+。

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env.example` 是可提交到 GitHub 的模板文件；真实密钥只写入本地 `.env`。不使用 LLM 中文研判时 API Key 可以留空；需要启用 DeepSeek、Qwen 或 OpenAI 报告生成时，再在 `.env` 中填写对应密钥。

```bash
DEEPSEEK_API_KEY=your_deepseek_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
AI_JUDGE_API_KEY=your_api_key_here
```

本项目公开仓库默认不上传 `data/raw/`、`data/processed/`、`data/vectors/`、`models/`、`outputs/`、`output/`、`reports/`、`.claude/` 等本地数据和生成产物；它们会保留在本机，但不进入 GitHub。

## 2. 当前默认主线

当前仓库默认主线配置为：

- 默认数据集：`harrison`
- 基础窗口：`50`
- 时序窗口：`50`
- 统计窗口：`30`
- 语义模式：`hash`
- 语义上下文窗口：`1`
- 默认 RAG 子集：`fox / harrison / santos`

## 3. 准备数据

如果需要下载公开样例数据：

```bash
python main.py --download
```

解析日志并提取特征：

```bash
python main.py --parse
python main.py --extract
```

## 4. 训练模型

完整训练：

```bash
python main.py --train --train-mode all
```

如需只评估主实验三视图与融合结果：

```bash
python main.py --evaluate-views --eval-datasets harrison,santos,fox
```

## 5. 构建活动 RAG 案例库

```bash
python main.py --build-rag --rag-force
```

说明：
- 当前默认活动数据集为 `fox / harrison / santos`
- 默认主实验入口不再指向 `hdfs`

## 6. 启动前端

```bash
python main.py --frontend
```

## 7. 前端推荐使用顺序

1. 上传日志文件
2. 调整风险阈值
3. 打开“快速定位高危日志”
4. 选择一条日志查看三段式证据链
5. 需要时再查看 RAG 相似案例和 LLM 报告

## 8. 一键完整流程

```bash
python main.py --all --train-mode all --with-rag --rag-force
```

## 9. 你现在最该关注的主线

- 主域内实验子集：`harrison`
- 主迁移目标子集：`santos`
- 补充分析子集：`fox`
- 主检测模型：`时序 + 语义（hash） + XGBoost`
- 统计视图定位：辅助分支
- RAG 用于检测后的相似案例辅助研判
