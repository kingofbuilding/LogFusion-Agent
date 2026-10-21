# LogFusion-Agent 快速开始

Python 3.10+，无需密钥的命令行演示：

```bash
python -m src.agent --demo
# 无需密钥的完整模拟链路：
python -m src.agent --demo --mode simulated
```

启动调查界面：

```bash
pip install -r requirements-agent.txt
streamlit run frontend/agent_app.py
```

配置本地 `.env` 中的 AGENT_API_KEY / AGENT_BASE_URL / AGENT_MODEL 后可选择 LLM 模式：

```bash
python -m src.agent --demo --mode llm
```

原项目训练、检测及 RAG 建库说明见 [docs/UPSTREAM_README.md](docs/UPSTREAM_README.md)，完整新功能说明见 [README.md](README.md)。
