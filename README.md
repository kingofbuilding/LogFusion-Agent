# LogFusion-Agent

**证据驱动的安全日志调查智能体**

基于 [LogFusion-LLM / public-upload](https://github.com/kingofbuilding/LogFusion-LLM/tree/public-upload) 演进，增加调查工具调用、事件关联、证据时间线和可追溯报告。原项目的多视图检测、融合和 RAG 源码保留；固定来源见 [UPSTREAM.md](UPSTREAM.md)。

第一版聚焦：**SSH 集中认证失败 → 同来源、同账号、同主机的后续成功登录 → 账户活动核查**。

## 两种运行方式

| 方式 | 如何决定下一步 | 条件 |
| --- | --- | --- |
| 规则调查演示 | 根据前序结果执行 SSH 剧本；无失败簇时跳过后续登录查询 | Python 3.10+，CLI 仅需标准库 |
| LLM Agent | 模型观察工具结果，每轮选择一个工具或结束 | 支持工具调用的模型及本地密钥 |

规则剧本不等于 LLM 自主规划。两者使用同一证据层，最终结论由已查询的日志按显式规则生成，模型负责选择工具。

## 快速体验

```bash
git clone https://github.com/kingofbuilding/LogFusion-Agent.git
cd LogFusion-Agent
python -m src.agent --demo
```

无需密钥或权重。结果位于 `outputs/investigations/INV-*/`，包含 `report.md` 与完整的 `investigation.json`。演示是合成日志，IP 使用文档保留地址，包含不同账号、主机和时间的干扰事件。

```bash
pip install -r requirements-agent.txt
streamlit run frontend/agent_app.py
```

工作台支持上传、调查目标、模式选择、执行进度、证据时间线、工具轨迹和 Markdown/JSON 下载。

## 使用 LLM Agent

复制 `.env.example` 为 `.env`，配置支持工具调用的服务：

```dotenv
AGENT_API_KEY=your_actual_key
AGENT_BASE_URL=https://api.deepseek.com
AGENT_MODEL=deepseek-chat
```

```bash
python -m src.agent --demo --mode llm
python -m src.agent --input path/to/auth.jsonl --mode llm --goal "调查 SSH 暴力破解和后续登录"
```

也可使用 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 及对应 Base URL。不要在实际 `.env` 中保留模板占位符。LLM 模式向配置的服务发送目标及部分日志；规则模式不外发日志。

## 六个只读工具

| 工具 | 能力 |
| --- | --- |
| `detect_anomalies` | 返回规则候选信号，或调用原项目检测模型 |
| `aggregate_events` | 按时间窗口、IP、账号、主机聚合认证失败 |
| `search_logs` | 查询完整日志，包括低风险的成功登录 |
| `get_event_context` | 查询已观察事件前后同账号、同主机活动 |
| `retrieve_cases` | 检索解释性案例，与事件事实分离 |
| `build_timeline` | 汇总已查询证据，保留来源、行号和事件 ID |

```mermaid
flowchart TD
    A[目标与日志] --> B[规则剧本 / LLM Agent]
    B --> C[只读工具调用]
    C --> D[全量日志 / 检测 / 案例]
    D --> E[证据与轨迹]
    E --> B
    B --> F[结束 / 达到预算 / 异常]
    F --> G[证据规则校验与关联]
    G --> H[发现、引用、时间线与不确定性]
```

## 输入与关联规则

支持 UTF-8 的 `.log`、`.txt`、`.jsonl`、`.json` 对象数组和 `.csv`。结构化输入需有 `message` / `log_text` / `raw` / `content`，可提供 `timestamp`、`host`、`src_ip`、`user`。

```json
{"timestamp":"2026-01-15T10:00:00Z","host":"server-a","message":"sshd[1]: Failed password for alice from 198.51.100.23 port 51000 ssh2"}
```

- 支持常见 SSH/sudo syslog；完整年份 ISO 时间参与关联。无时区按 UTC；年不完整时不猜测年份。
- 同 IP、账号、主机 5 分钟内至少 5 次失败，标为疑似暴力破解；关联失败簇结束后 15 分钟内成功登录，再查后续 15 分钟账户上下文。
- 每个实体仅检查最密集失败窗口；规则剧本最多调查 3 组、深入查询 3 条成功登录。截断会披露。
- 最大 20 MiB / 100000 条；单条最多 32768 字符。
- 未允许字段（包括攻击标签与人工结论）不进入工具；原始 message 若包含答案或敏感信息，导入前仍需处理。

## 复用原检测与 RAG

训练和建索引方式见 [原项目说明](docs/UPSTREAM_README.md)。

```bash
pip install -r requirements.txt
# 按原说明准备数据、训练模型并构建案例索引后：
python -m src.agent --input path/to/auth.jsonl --with-detector --vector-rag
streamlit run frontend/app.py
```

原界面新增默认的 Agent 调查入口。公开仓库不含权重和私有日志。默认后端明确标记 `rule_signals` 和 `lexical_case_search`，不伪称训练模型或向量 RAG。显式启用模型/索引但文件缺失时会报错。

原检测器的窗口分数映射到末行事件 ID。各视图仍遵循上游代理分数与 hash 回退逻辑；融合模型存在不代表所有视图模型已训练加载。

## 预算与边界

```bash
python -m src.agent --demo --max-steps 16 --max-seconds 90 --max-tokens 24000
```

- 设轮数、累计 token、重复调用、工具错误限制，记录停止原因。
- 时间/token 在调用之间及模型返回后检查；在途调用可能超限，因此不是严格费用上限。单次输出上限 1200 tokens，网络默认超时 20 秒，无自动重试。
- 模型每次最多查看 20 条事件预览，每条原文 600 字符；完整已查证据保留在 JSON。
- 支持结果保存，尚无进程重启后的恢复；同步 UI 暂无取消按钮。
- 没有自动封禁、Shell 或主机操作能力。上传文本作为不可信数据；工具白名单与证据规则不代表所有提示注入都已彻底解决。
- 成功登录不等于入侵成功，sudo 不等于恶意提权，未发现后续活动不等于证明安全。

## 验证

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python -m src.agent --demo
```

覆盖实体误关联、时间窗口、完整流查询、引用、标签隔离、预算、模型工具调度与导出。LLM 测试使用模拟服务；真实模型质量尚需事件级评估，见 [设计与评估规划](docs/AGENT_DESIGN.md)。

## 许可证

MIT，保留原项目许可。来源见 [UPSTREAM.md](UPSTREAM.md)。

默认 Agent 案例库位于 `data/agent/reference_cases.jsonl`，只使用上游内置通用案例，不使用从带标签实验日志抽取的模板。可选原向量 RAG 仍应自行审核其案例来源，避免评测泄漏。
