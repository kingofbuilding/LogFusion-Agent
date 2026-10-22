# 功能修改记录

> 说明：从当前版本开始，后续每次进行功能修改、规则调整、前端重构、RAG 重建或实验链路改动，都应在本文件中追加记录，便于论文撰写、版本回溯与答辩说明。

---

## 2026-05-29

### 修改内容
- 整理项目为可公开上传 GitHub 的文件状态，保留本地数据和生成产物但不纳入 Git 跟踪。
- 脱敏 `.env.example` 中的 DeepSeek API Key 示例，将真实风格密钥替换为占位符。
- 脱敏 `configs/config.yaml` 中的 AI Judge Profile API Key 字段，保留 provider/model/base_url 配置但将密钥置空。
- 补强 `.gitignore`，忽略 `.env`、`.claude/`、本地数据、模型、输出、报告、缓存和常见大文件格式。
- 更新 `README.md` 与 `QUICKSTART.md`，补充 Python 版本建议、`.env` 配置方式、公开仓库不上传目录和密钥提交注意事项。
- 新增 MIT `LICENSE` 文件。

### 修改原因
- 当前目录混有源码、实验结果、论文材料、模型输出和本地状态文件，需要整理出可直接上传 GitHub 的公开项目范围，同时不删除用户本地已有数据。

### 影响模块
- configs/config.yaml
- .env.example
- .gitignore
- README.md
- QUICKSTART.md
- LICENSE
- FUNCTION_UPDATE_LOG.md

### 结果说明
- GitHub 公开版本将以源码、配置模板、文档和安全示例数据为主体；本地数据、输出、报告和 Claude 状态文件保留在本机但默认不上传。
- 如疑似 API Key 曾真实可用，仍建议在服务商后台吊销或轮换。

### 编码检查
- 待执行 `python main.py --help` 与 `python -m compileall main.py frontend src`。

### Git 状态
- 待提交

## 2026-05-25

### 修改内容
- 修复前端上传日志解析展示时，RAG 辅助分类缺少“/子类”结构导致 `攻击子类` 列未创建的问题。
- 在检测结果视图构建阶段提前初始化“攻击大类”和“攻击子类”列，并在细粒度分类升级处对“攻击子类”使用安全兜底读取，避免缓存或合并路径导致字段缺失时访问不存在字段。

### 修改原因
- 上传普通 log 文件后，部分 RAG 分类只有攻击大类没有子类，触发 `KeyError: '攻击子类'`，导致 Streamlit 检测页面中断。

### 影响模块
- frontend/runtime.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 日志上传解析路径在 RAG 分类无子类时会保留空子类字段并继续渲染，不再因为缺列崩溃。

### 编码检查
- 已执行 `python -m py_compile frontend/runtime.py`，通过。

### Git 状态
- 未提交

## 2026-05-14

### 修改内容
- 根据桌面论文 DOCX `降ai5120220846_周宇轩_信息安全_基于大模型与多视图融合技术的安全日志分析助手_宋丽丽孙海峰.docx` 提取正文、表格和内嵌图片。
- 新增本科毕业答辩 PPT 输出包：`output/defense_ppt_20260514/final_presentation_cn.pptx`。
- PPT 共 14 页，覆盖研究背景、研究目标、总体架构、多视图融合方法、RAG/AI Judge 研判增强、实验设计、关键结果、系统展示和总结展望。
- 生成素材清单与质量检查报告：`output/defense_ppt_20260514/asset_manifest.md`、`output/defense_ppt_20260514/qa_report.md`。
- 在原版 PPT 基础上新增学术化增强版：`output/defense_ppt_20260514/final_presentation_cn_academic_v2.pptx`，优化标题结论化、术语规范性、方法边界和证据表达。
- 按 Nature-style 学术答辩风格重构生成新版 PPT：`output/defense_ppt_20260514/final_presentation_cn_nature_rebuild.pptx`，重做封面、汇报主线、章节页、方法页、结果页证据层级、系统展示页和总结页。
- 使用 Python/matplotlib 重绘答辩核心图形资产并生成图形增强版 PPT：`output/defense_ppt_20260514/final_presentation_cn_nature_figures.pptx`；新增总体技术路线图、三视图融合机制图、统计子分数 F1 图、监督式融合器 F1 图和系统闭环图。

### 修改原因
- 为毕业论文答辩准备可直接使用的中文演示文稿，突出方法设计、实验结果和系统实现闭环。

### 影响模块
- output/defense_ppt_20260514/final_presentation_cn.pptx
- output/defense_ppt_20260514/final_presentation_cn_academic_v2.pptx
- output/defense_ppt_20260514/final_presentation_cn_nature_rebuild.pptx
- output/defense_ppt_20260514/final_presentation_cn_nature_figures.pptx
- output/defense_ppt_20260514/nature_figures/
- output/defense_ppt_20260514/qa_report.md
- output/defense_ppt_20260514/qa_report_academic_v2.md
- output/defense_ppt_20260514/qa_report_nature_rebuild.md
- output/defense_ppt_20260514/qa_report_nature_figures.md
- output/defense_ppt_20260514/asset_manifest.md
- output/defense_ppt_20260514/generate_defense_ppt.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已通过 `python-pptx` 重新打开验证，原版与学术化增强版 PPT 均为 14 页；Nature-style 重构版为 16 页；重绘图增强版为 16 页，嵌入 5 张新绘核心图。
- 当前环境未执行 PowerPoint/LibreOffice 整页渲染预览，建议最终提交前本机快速翻页检查。

### 编码检查
- 不涉及业务代码。

### Git 状态
- 未提交

## 2026-05-13

### 修改内容
- 查看毕业论文检测报告目录，梳理查重、AIGC、格式和智评报告的核心指标。
- 新增检测报告分析与修改建议文档：`reports/论文检测报告分析与修改建议_20260513.md`。
- 汇总当前主要风险：查重安全、AIGC 疑似占比较高、格式一般错误较多、智评建议补强机制解释与系统鲁棒性。

### 修改原因
- 为论文终稿提交前的降 AIGC、格式修正和内容补强提供可执行修改顺序。

### 影响模块
- reports/论文检测报告分析与修改建议_20260513.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已生成 Markdown 版指导意见，便于后续直接按章节修改论文。

### 编码检查
- 不涉及代码。

### Git 状态
- 未提交

## 2026-05-11

### 修改内容
- 对桌面文档 `降ai版.docx` 进行毕业论文审稿与学术润色，保留原文档不覆盖。
- 导出润色版 Word 文档与独立审稿意见说明：`output/doc/降ai版_审稿润色版.docx`、`output/doc/降ai版_审稿意见与修改说明.md`。
- 修正论文中的明显重复句、漏标点、表格表头重复、表格说明缺失和致谢部分过度口语/文学化表达。
- 按“只改正文段落文字、不动表格/图片/页眉页脚/公式”的规则，重新导出保模板降 AI 版本：`output/doc/降ai版_保模板降AI润色版.docx`。
- 新增保模板降 AI 修改说明，记录整段替换位置与修改原因：`output/doc/降ai版_保模板降AI修改说明.md`。
- 根据用户标出的高 AI 率段落进行第二轮定点改写，继续遵循“只改正文段落文字、不动表格/图片/页眉页脚/公式”的约束。
- 导出第二轮保模板降 AI 版本与修改说明：`output/doc/降ai版_保模板降AI润色版_v2.docx`、`output/doc/降ai版_保模板降AI修改说明_v2.md`。
- 根据用户追加标出的 12 处高 AI 率段落进行第三轮定点改写，覆盖摘要、绪论、相关工作、实验参数、系统实现和总结部分。
- 导出第三轮保模板降 AI 版本与修改说明：`output/doc/降ai版_保模板降AI润色版_v3.docx`、`output/doc/降ai版_保模板降AI修改说明_v3.md`。
- 面向全文进行第四轮综合降 AI 改写，重点消除序号化表达（第一/第二/第三）、"需要说明的是"、公式化连接词、"针对...问题"、"该研究/该方法"、"首先...其次...最后"等高频 AI 标志，覆盖方法设计、实验分析、系统实现和总结展望全部章节。
- 导出第四轮保模板降 AI 版本与修改说明：`output/doc/降ai版_保模板降AI润色版_v4.docx`、`output/doc/降ai版_保模板降AI修改说明_v4.md`。

### 修改原因
- 降低论文文本中的机械化表达和 AI 痕迹，提高毕业论文表达的自然度、严谨性和可提交性。

### 影响模块
- output/doc/降ai版_审稿润色版.docx
- output/doc/降ai版_审稿意见与修改说明.md
- output/doc/降ai版_保模板降AI润色版.docx
- output/doc/降ai版_保模板降AI修改说明.md
- output/doc/降ai版_保模板降AI润色版_v2.docx
- output/doc/降ai版_保模板降AI修改说明_v2.md
- output/doc/降ai版_保模板降AI润色版_v3.docx
- output/doc/降ai版_保模板降AI修改说明_v3.md
- output/doc/降ai版_保模板降AI润色版_v4.docx
- output/doc/降ai版_保模板降AI修改说明_v4.md
- tmp/docs/polish_docx.py
- tmp/docs/preserve_template_deai.py
- tmp/docs/high_ai_second_pass.py
- tmp/docs/high_ai_third_pass.py
- tmp/docs/high_ai_fourth_pass.py

### 结果说明
- 已通过 `python-docx` 重新打开验证，原桌面文件未覆盖。
- 当前环境缺少 LibreOffice/Poppler，未执行 PDF/PNG 页面渲染检查。

### 编码检查
- 已检查

### Git 状态
- 未提交

## 2026-05-06

### 修改内容
- 新增第 4 章“RAG 与大语言模型研判增强流程图”绘图脚本。
- 导出论文用 PNG 与 SVG 流程图，展示高风险窗口、研判输入构造、相似案例检索、证据门控、AI Judge 生成、规则回退与前端展示导出流程。
- 新增第 3 章“时序视图建模流程示意图”绘图脚本，导出 PNG 与 SVG，展示 Drain 模板 ID、窗口序列、Embedding、Bi-LSTM、Attention、风险分输出和融合层输入流程。
- 优化 RAG 研判增强流程图与时序视图流程图的论文版式，将主链路、检索支路、模型调用支路和中间表示区域分区排布，减少长斜线、交叉线和文字遮挡。
- 保留原始导出图片，新增 refined 版本文件名输出，便于保留论文图片创作与迭代过程。
- 从终稿 `lunwen.docx` 提取正文文本到 `reports/final_thesis_package/lunwen_docx_extracted_20260506.txt`，用于论文终稿质量检查。
- 重新提取最新版 `lunwen.docx` 正文到 `reports/final_thesis_package/lunwen_docx_extracted_latest_20260506.txt`，用于复核论文结构优化点。
- 新增第 4 章证据门控机制与规则回退机制补充文档，用于增强 RAG 与大模型研判增强方法章节。
- 新增终稿论文补充与压缩建议文档，梳理第 4 章补强方向和第 1、2、5、6 章压缩空间。
- 新增第 3 章统计子分数计算方式说明文档，明确统计子分数由分组特征归一化聚合得到，而非独立 Isolation Forest 模型输出。
- 新增专家审阅意见回应与修订建议文档，逐条判断格式、实验协议、摘要口径和滑动窗口泄露等问题的处理方式。

### 修改原因
- 补充第 4 章研判增强方法的流程化表达，使 RAG、证据门控、大语言模型和规则回退之间的关系更直观。
- 补充第 3 章时序视图内部建模流程，使 Bi-LSTM + Attention 的输入、编码、加权和输出关系更便于论文展示。

### 影响模块
- reports/final_thesis_package/generate_rag_llm_enhancement_flow_20260506.py
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig4_rag_llm_enhancement_flow_20260506.png
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig4_rag_llm_enhancement_flow_20260506.svg
- reports/final_thesis_package/generate_temporal_view_flow_20260506.py
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig3_temporal_view_modeling_flow_20260506.png
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig3_temporal_view_modeling_flow_20260506.svg

### 结果说明
- 已通过 `python -m py_compile` 语法检查。
- 已生成白底黑字论文风格流程图。

### 编码检查
- 已检查

### Git 状态
- 未提交

## 2026-05-05

### 修改内容
- 重绘第 6 章“安全日志分析助手系统总体架构图”，将原偏方法链路的表达调整为“三栏式”软件系统架构图。
- 更新 `reports/final_thesis_package/generate_project_architecture_reference_20260505.py`，重新导出 PNG 与 SVG 论文插图。
- 新图按“用户与前端交互层—后端检测与研判服务层—数据、模型与外部资源层”组织模块，弱化算法内部流程，突出系统实现边界。
- 按论文制图风格进一步去除小图标和灰底填充，保留白底黑字、矩形模块和少量主箭头，减少文字遮挡。
- 优化箭头布局为总线式资源连接和短纵向主链路箭头，移除箭头说明文字，避免连线文字遮挡。
- 按检测主链路与研判增强链路语义修正右侧资源箭头：日志读取/写入、特征表生成、模型加载推理、RAG 相似检索、LLM 交互调用和结果导出分别指向对应资源。
- 根据目标参考图重排整体版式：采用三栏大框、五个后端服务框、右侧六类资源框和居中箭头标签，进一步贴近论文白底黑字架构图风格。

### 修改原因
- 区分第 3 章方法总体框架图与第 6 章系统总体架构图，避免两者在布局上雷同。
- 第 6 章插图应突出前端交互、后端服务、数据模型资源、外部 LLM 调用和报告导出等工程组成，而不是重复展示检测方法内部的数据流。

### 影响模块
- reports/final_thesis_package/generate_project_architecture_reference_20260505.py
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig6_1_project_architecture_reference_20260505.png
- reports/final_thesis_package/figures_lunwen_publication_20260504/fig6_1_project_architecture_reference_20260505.svg

### 结果说明
- 已通过 `python -m py_compile` 语法检查。
- 已重新生成论文用系统总体架构图。

### 编码检查
- 已检查

### Git 状态
- 未提交

## 2026-03-29

### 本次整理内容

1. 重写 `README.md`
   - 修复旧版中文乱码
   - 按当前主实验口径更新项目说明
   - 更新命令、目录结构、功能范围和相关文档链接

2. 重写 `QUICKSTART.md`
   - 修复旧版中文乱码
   - 只保留当前可直接运行的最短路径
   - 明确默认数据集和 RAG 重建入口

3. 新建 `FUNCTION_UPDATE_LOG.md`
   - 作为后续功能修改和版本迭代的统一记录入口

### 后续记录建议格式

每次新增记录建议包含以下内容：

- 日期
- 修改范围
- 修改原因
- 影响模块
- 是否涉及训练结果重跑
- 是否涉及前端展示变化
- 是否检查乱码/编码
- 是否已提交 GitHub

### 模板

```text
## YYYY-MM-DD

### 修改内容
- ...
- ...

### 修改原因
- ...

### 影响模块
- frontend/...
- src/...
- reports/...

### 结果说明
- ...

### 编码检查
- BAD=0 / 已检查

### Git 状态
- 已提交 / 未提交
```

## 2026-04-05

### 修改内容
- 重写第 5 章实验分析正文，清除残留乱码和占位段落，补齐排序能力与 RAG 检索效果分析
- 新增第 3 章方法设计正文，统一当前系统实现口径
- 对前端演示链路进行回归验证，包括上传解析、检测、视图构造和 Streamlit 首页可访问性检查

### 修改原因
- 论文正文需要从“结果堆积”收敛到可直接写入的正式版本
- 第 5 章原稿仍有残留乱码和未完成段落，不适合继续沿用
- 需要确认当前前端链路已达到可演示状态，仅保留真正影响展示的问题进入后续修复范围

### 影响模块
- reports/final_thesis_package/chapter3_method_design.md
- reports/final_thesis_package/chapter5_experiment_analysis.md
- README.md
- QUICKSTART.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 第 3 章和第 5 章现已形成可直接用于论文撰写的正文版
- 前端首页可正常启动并通过本地访问验证
- 上传日志后的检测主链可完成数据构造与结果输出，当前未发现新的阻断性展示问题

### 编码检查
- README.md BAD=0
- QUICKSTART.md BAD=0
- FUNCTION_UPDATE_LOG.md BAD=0
- chapter3_method_design.md BAD=0
- chapter5_experiment_analysis.md BAD=0

### Git 状态
- 待提交

## 2026-04-30

### 修改内容
- 新增实验环境与关键参数补充文本，包含硬件、软件依赖、Isolation Forest、Bi-LSTM、语义哈希表示和 XGBoost 参数。

### 修改原因
- 论文第 5 章实验环境段落存在待补占位，需要按当前配置和本机环境补齐可直接粘贴的正式文本。

### 影响模块
- reports/final_thesis_package/experiment_env_params_fill_20260430.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已生成可直接写入论文的段落和“表 5-1 实验环境与关键参数设置”。
- 已补充第 5.3 数据集与样本构造、第 5.4 评价指标正式稿，明确窗口大小、滑动步长、标签规则、三视图样本构造和 65%/15%/20% 时序切分协议。
- 已润色第 3.1 总体框架设计，统一“检测主链路 + RAG/LLM 研判增强链路”的论文表述。
- 已优化第 3.2 统计视图设计，补齐固定滑动窗口、统计短窗口、行为上下文、实际统计特征和 Isolation Forest 参数。
- 已优化第 3.3 时序注意力视图设计，补齐模板 ID embedding、Bi-LSTM + Attention 结构、训练参数和时序风险分计算。

### 编码检查
- 未单独执行

### Git 状态
- 待提交

## 2026-04-05（续）

### 修改内容
- 新增第 4 章 RAG 与大模型研判增强正文，统一当前案例型 RAG 实现与论文表述
- 对第 3/4/5 章正文文件进行编码回读检查，确认无乱码

### 修改原因
- 论文主体章节需要连续成型，避免方法、实验和 RAG 增强之间表述脱节
- 需要将当前系统中的案例检索增强、LLM 报告生成和检测主链关系准确写入正文

### 影响模块
- reports/final_thesis_package/chapter4_rag_llm_analysis.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 第 3、4、5 章现已形成连续的论文正文基础版本
- 第 4 章内容与当前实现一致，明确 RAG 为检测后的案例检索增强，而非全量问答型 RAG

### 编码检查
- chapter3_method_design.md BAD=0
- chapter4_rag_llm_analysis.md BAD=0
- chapter5_experiment_analysis.md BAD=0
- FUNCTION_UPDATE_LOG.md BAD=0

### Git 状态
- 待提交

## 2026-04-05 统计视图补强
- 为统计视图补充了面向安全场景的代理特征：`auth_failure_ratio`、`auth_success_ratio`、`privileged_command_ratio`、`web_probe_ratio`、`suspicious_keyword_ratio`。
- 将统计特征提取链路接入 `S_train/S_test` 序列文本。
- 在 `harrison` 子集上重新训练 Isolation Forest，并重跑视图评估流程。
- 结果表明：统计视图单独效果仍然有限，但补强后的分支已在若干融合变体中带来可测的增益。

## 2026-04-05 DNS 统计特征验证
- 面向 `harrison` 场景补充了 DNS 代理特征：`dns_query_ratio`、`dns_forwarded_ratio`、`dns_refused_ratio`、`dns_long_token_ratio`、`dns_query_reply_mix`。
- 验证发现，这批特征能够在 `harrison` 的正样本窗口中激活，并与数据集中 dnsmasq 较密集的异常序列相吻合。
- 重新训练 Isolation Forest，并再次评估 `harrison`。统计视图的 AUC 有所提升，但融合结果未继续改善，说明这批 DNS 特征更适合作为辅助排序信号，而不是提升统计分支最终权重的主要路径。
- 结果文件：`reports/final_thesis_package/statistical_view_harrison_dns_delta.csv`、`reports/final_thesis_package/statistical_view_harrison_dns_refresh_report.md`。

## 2026-04-08 默认语义模式统一为 Hash
- 将 `configs/config.yaml` 中的 `features.semantic.force_hash_fallback` 设置为 `true`。
- 使前端、训练脚本和论文口径中的默认语义模式与当前主实验线保持一致。
- 当前语义视图仍以序列蒸馏文本为输入，但默认编码器已由 `sentence-transformers` 切换为基于 `hash` 的实现。

## 2026-04-08 主体行为统计试验
- 在代码中新增了试验性主体行为统计特征：`requests_per_ip`、`unique_uri_per_ip`、`failed_login_per_user`、`unique_port_per_ip`、`session_length`、`mean_interval_per_ip`。
- 在 `harrison` 子集上重跑后确认，部分主体行为特征已经出现有效信号，但当前 `Isolation Forest + proxy blend` 路径尚不能将这些信号稳定转化为更强的统计分支能力。
- 因此保留代码实现，同时将这批试验特征从当前默认配置中撤下，以避免影响论文主实验主线和前端演示稳定性。
- 试验总结：`reports/final_thesis_package/statistical_behavior_feature_trial_report.md`。

## 2026-04-09 语义上下文窗口完整曲线补充
- 新增 `window=10` 复测，并将 `window=1/2/4/6/10` 五组结果整合为统一总表。
- 新增完整指标文件：`reports/final_thesis_package/semantic_context_window_all_compare.csv`。
- 新增安全查看版：`semantic_context_window_all_compare_safe.xlsx` 与 `semantic_context_window_all_compare_safe.html`。
- 新增 `semantic_score` 分布摘要：`semantic_context_window_distribution_summary.csv`。
- 新增泄漏检查说明：`semantic_context_window_leakage_check.md`。
- 结论更新：在当前 AIT-LDS v2 数据、`hash` 语义模式、基础窗口 50、时序窗口 50、统计窗口 30 的设置下，`window=1` 在 `harrison`、`santos`、`fox` 三个子集上均优于 `2/4/6/10`。

## 2026-04-09 默认主线配置收口
- 将 `configs/config.yaml` 中的默认统计窗口从 `50` 调整为 `30`。
- 将默认语义上下文窗口从 `10` 调整为 `1`。
- 保持基础窗口 `50`、时序窗口 `50` 不变。
- 重写 `README.md` 与 `QUICKSTART.md`，统一当前最稳主线口径。
- 当前默认配置正式收口为：基础窗口 `50`、时序窗口 `50`、统计窗口 `30`、语义模式 `hash`、语义上下文窗口 `1`。

## 2026-04-12 前端默认告警阈值调整
- 将前端默认风险告警阈值由 `0.50` 调整为 `0.68`，使日常调试、截图与答辩展示更贴近当前主实验阈值区间。
- 同时将 `apply_domain_thresholds` 默认改为 `false`，避免界面显示为 `0.68` 时后台仍自动按安全域 `0.45` 执行，造成“显示阈值”与“实际阈值”不一致。
- 原有 `domain_thresholds` 配置继续保留，后续如需恢复按域自动阈值策略，可直接重新启用。

## 2026-04-17 统计视图拆分子分融合实验
- 在评估链中将统计视图拆分为 `stat_dist_score`、`stat_auth_score`、`stat_web_score` 和 `stat_dns_score` 四个子统计分数。
- 分别测试了：
  - `xgboost_fusion_stat_parts_xgb`
  - `xgboost_fusion_stat_parts_plus_legacy_xgb`
- 结果显示，拆分子分数后，融合效果在 `harrison`、`santos`、`fox` 三个子集上均显著优于原始 `xgboost_fusion_retrained`。
- 该结果说明统计信息并非无效，而是原来的单一 `stat_score` 表达过粗，导致不同异常模式在同一分数中相互抵消。
- 新增正式实验结果文件：
  - `outputs/reports/stat_parts_fusion_eval_20260417.csv`
  - `outputs/reports/stat_parts_fusion_eval_20260417.json`
  - `outputs/reports/stat_parts_fusion_focus_20260417.csv`
  - `reports/final_thesis_package/stat_parts_fusion_report.md`

## 2026-04-20 README 主线口径校正

### 修改内容
- 复核当前实验产物、协议常量与论文表格/图表构建脚本，确认最新论文实验主线已切换到 `truncated_ordered_pre_split_v1`。
- 更新 `README.md` 的“当前主线配置”，将旧的 `ordered_pre_split` 主线表述改为“论文实验主线 vs 前端默认运行口径”两层说明。
- 修正 README 中的前端默认阈值描述，由旧的 `0.5` 改为当前配置中的 `0.68`。

### 修改原因
- 用户已完成主实验重跑，README 中仍保留旧主线口径，容易把论文实验协议和前端默认配置混淆。
- 需要让仓库首页说明与当前实验产物、表格构建脚本和配置现状保持一致。

### 影响模块
- README.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- README 现已明确：论文实验主线采用 `truncated_ordered_pre_split_v1`，而前端默认配置仅代表演示入口，不再等同于论文主线。
- 仓库首页对主线协议、默认阈值和实验/前端口径的说明已与当前状态一致。

### 编码检查
- README.md 已通过 UTF-8 回读

### Git 状态
- 待提交

## 2026-04-20 前端视觉风格收敛

### 修改内容
- 统一 `frontend/theme.py` 的全局视觉变量与 Streamlit 样式，改为浅色极简的企业级风格。
- 调整 `frontend/app.py` 的侧边栏、上传区与工作台模式文案，去掉多余 emoji 和偏演示化表达。
- 重写 `frontend/helpers.py` 中的 Hero 与 KPI 卡片样式，使首页第一屏更克制、更适合答辩与演示。
- 在 `frontend/panels.py` 中统一总览页、RAG 卡片、研判中心关键结论卡与关键词标签的视觉语言。
- 继续收敛 `frontend/panels.py` 的总览页与技术分析页，按“全局态势 / 风险构成 / 融合关系”与“风险分布 / 视图贡献 / 高风险样本”重组信息层级。
- 将 `configs/config.yaml` 的前端默认 `split_mode` 从 `ordered_pre_split` 调整为 `truncated_ordered_pre_split`，并同步修正 README 中的默认运行口径说明。
- 继续收敛 `frontend/panels.py` 的高危定位与三段式证据链区域，统一筛选区、结果区、单条事件证据链与 RAG 候选卡片的容器层级和视觉样式。
- 继续收敛 `frontend/panels.py` 的事件详情、事件级研判报告与 AI 深度问答区域，统一摘要卡、引擎状态区、证据区和导出操作区的层级与文案。
- 新增基于现有 Streamlit 工作台的 API 管理后台雏形：在“模型与规则管理”页支持 `ai_judge` 的 Profile 编辑、连接测试、YAML 持久化与当前运行态展示。
- 为连接测试补充向后兼容逻辑：即使当前前端进程里的 `AIJudge` 还是旧实例、没有 `test_connection()` 方法，也可通过运行态状态与最小请求完成测试，避免页面直接报错。
- 扩展 `src/utils/common.py`、`frontend/runtime.py` 与 `src/rag/ai_judge.py`，补齐配置写回、Profile 解析、运行态状态输出和最小化连通性测试能力。

## 2026-04-23 BGL DeepLog protocol 进一步向论文口径收口

### 修改内容
- 将 `benchmarks/public_logs/preprocess_bgl.py` 的 BGL 序列缓存文件改为带 `window/stride` 参数后缀，避免不同构窗参数复用同一 `bgl_sequences.csv`。
- 将 `benchmarks/configs/bgl.yaml` 默认 `stride_minutes` 从 `5` 恢复为 `1`，并新增 `benchmarks.public_logs.deeplog_threshold_r` 配置项。
- 扩展 `benchmarks/models/temporal_public.py`，为 `score_temporal_public(...)` 增加 `fixed_threshold` 入口，使 protocol runner 可绕开 `val` 搜阈值。
- 扩展 `benchmarks/runners/_deeplog_protocol_common.py`，新增 `threshold_r` 与 `use_val_split` 协议参数；BGL 可改为“前 5000 条正常序列训练 + 剩余序列直接测试”。
- 更新 `benchmarks/runners/run_bgl_deeplog_protocol.py`：强制使用 `LSTM`、`5-minute window + 1-minute stride`、`use_val_split=False`，并显式输出固定 `r` 协议。

### 修改原因
- 用户明确要求优先收口 BGL 与论文版 DeepLog 的关键协议差异，当前实现最主要偏差是 `stride=5`、仍保留 `val` 切分、以及 `r` 通过 `val` F1 搜索得到。
- 旧的 BGL sequence 缓存文件名未编码协议参数，会导致修改步长后仍可能复用旧序列结果，影响审计结论。

### 影响模块
- benchmarks/public_logs/preprocess_bgl.py
- benchmarks/models/temporal_public.py
- benchmarks/runners/_deeplog_protocol_common.py
- benchmarks/runners/run_bgl_deeplog_protocol.py
- benchmarks/configs/bgl.yaml
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 BGL paper-protocol runner 已切换为更接近论文描述的 `5-minute window + 1-minute stride + normal-only 5000 + no val split + explicit r` 路径。
- 新结果仍需以本轮重跑输出为准，不再沿用旧 `stride=5 / val-threshold` 结果解释论文对齐表现。

### 编码检查
- `python -m py_compile` 已通过：
  - `benchmarks/public_logs/preprocess_bgl.py`
  - `benchmarks/models/temporal_public.py`
  - `benchmarks/runners/_deeplog_protocol_common.py`
  - `benchmarks/runners/run_bgl_deeplog_protocol.py`

### Git 状态
- 待提交

## 2026-04-23 三视图模型接入 BGL protocol 小样本验证

### 修改内容
- 新增 `benchmarks/models/my_model_public.py`，将 benchmark sequence DataFrame 适配为 `ThreeViewScoringService.score(...)` 所需输入，并输出 statistical / temporal / semantic 三路分数与固定均值融合分数。
- 新增 `benchmarks/runners/run_bgl_my_model_protocol.py`，复用 BGL protocol 的同一序列构造与训练样本数设置，对三视图固定融合做小样本 smoke test。
- 当前固定融合规则为三路归一化分数的等权平均，不引入监督式 XGBoost。

### 修改原因
- 用户要求先在与 DeepLog 相同 benchmark 思路下，对自己的无监督三视图模型做小样本测试。
- strict normal-only 场景下不应先把监督式 XGBoost 融合混入正式协议结果，因此先落固定规则融合版本。

### 影响模块
- benchmarks/models/my_model_public.py
- benchmarks/runners/run_bgl_my_model_protocol.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已具备直接运行 BGL 三视图 protocol 小样本测试的最小闭环。
- 结果需以本轮 smoke test 输出为准，再决定是否扩到 HDFS 和完整正式 runner。

### 编码检查
- `python -m py_compile` 已通过：
  - `benchmarks/models/my_model_public.py`
  - `benchmarks/runners/run_bgl_my_model_protocol.py`

### Git 状态
- 待提交

## 2026-04-23 BGL 三视图 protocol 输出补齐分视图结果

### 修改内容
- 更新 `benchmarks/runners/run_bgl_my_model_protocol.py`，不再只输出单条 fusion 结果，而是同时输出 statistical / temporal / semantic / fusion 四条结果。
- 在同一 JSON 中按 `metrics.statistical / temporal / semantic / fusion` 分别记录四类指标，便于直接分析各视图贡献。
- 继续沿用同一 BGL protocol：`5-minute window + 1-minute stride + train_normal_sequences=5000`。

### 修改原因
- 用户明确要求 BGL 结果不能只看融合分，必须同时保留全部视图及融合分数，便于判断是哪一路在拉高最终结果。

### 影响模块
- benchmarks/runners/run_bgl_my_model_protocol.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 BGL my-model protocol 输出已具备分视图可读性，可直接对比单路与融合的差异。

### 编码检查
- 待本轮 `py_compile`

### Git 状态
- 待提交

## 2026-04-23 BGL temporal score 向 DeepLog 靠拢

### 修改内容
- 在 `benchmarks/models/temporal_public.py` 中新增 `deeplog_true_prob_mean` score mode。
- 新 score 的 step-level 定义改为 `1 - P(true_next_event)`，并以 sequence mean 聚合，保持 `val` 选阈值、`test` 评估。
- 在 `benchmarks/runners/run_bgl_public.py` 中新增结果行 `temporal_public_bgl_deeplog`，且在 BGL JSON 中新增 `temporal_deeplog_score_mode`。
- 同步更新 `README_public_benchmarks.md` 与 `reports/bgl_protocol_alignment_report.md`，明确这是更接近 DeepLog 的 scoring 对照，不是完整论文复现。

### 修改原因
- 当前 BGL temporal 训练范式已经接近 DeepLog，主要差异在 sequence anomaly score 定义。
- 需要在不改变 BGL 主干协议的前提下，把 temporal scoring 调得更接近 DeepLog，便于与当前仓库口径并排比较。

### 影响模块
- benchmarks/models/temporal_public.py
- benchmarks/runners/run_bgl_public.py
- README_public_benchmarks.md
- reports/bgl_protocol_alignment_report.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- BGL 现在可同时输出三种 temporal 口径：`temporal_public`、`temporal_public_bgl_sequence`、`temporal_public_bgl_deeplog`。
- 本轮仍保持 BGL 的排序、构窗、ordered split 与 train normal-only 协议不变。
- 新增对照只改变 score 定义，不重写 backbone，也不宣称严格复现 DeepLog。

### 编码检查
- benchmarks/models/temporal_public.py 已通过 `py_compile`
- benchmarks/runners/run_bgl_public.py 已通过 `py_compile`

### 结果补充
- 后续追加 BGL fusion 对照：将 `temporal_public_bgl_deeplog` 接入 `fusion_public_mean` 与 `fusion_public_weighted`，用于直接观察融合是否上涨。
- 为避免每次对照都重跑全量 BGL，新增 split 级子样本开关：`max_train_samples`、`max_val_samples`、`max_test_samples`，用于快速验证融合方向。
- 当前将 `benchmarks/configs/bgl.yaml` 临时切到小样本验证配置：train=4000、val=1500、test=1500，用于快速比较 fusion 走势。
- 将 `benchmarks/models/temporal_public.py` 的 scoring 改为 batch 化前向，避免逐序列逐步单条推理导致的小样本验证仍然过慢。
- 新增 `fusion_bgl_stat_temp_deeplog`，直接测试去掉 semantic 后的 `stat + temporal_deeplog` 两路 fusion，判断 semantic 是否是当前主要拖累项。
- 当前工作已转向 temporal-only：在 `temporal_public.py` 中新增 `deeplog_true_prob_topk_mean`、`deeplog_true_prob_min`、`deeplog_nll_topk_mean`，并在 BGL runner 中只保留 temporal 对照作为本轮重点观察对象。

### Git 状态
- 待提交

## 2026-04-23 三视图无监督 benchmark 独立试验文件

### 修改内容
- 新增 `benchmarks/models/my_model_public_unsupervised.py`，将三视图 benchmark 适配器独立为无监督试验版本。
- 新版本不再使用各 split 各自归一化与 `val` 标签搜阈值，改为基于 `train normal` 分布做 percentile 校准，并以 train quantile 直接给出阈值。
- 新增 `benchmarks/runners/run_hdfs_my_model_protocol_unsupervised.py`，用于单独运行 HDFS 三视图无监督 protocol，对外输出 statistical / temporal / semantic / fusion 四路指标。
- 保持原 `benchmarks/models/my_model_public.py` 与原 runner 不变，避免把试验版逻辑混入既有 benchmark 主线。

### 修改原因
- 用户明确要求“另开一个 py 文件”，并希望先试一版更接近 DeepLog 风格的无监督三视图，再跑小样本验证。
- 当前原实现依赖 split 内归一化和 `val` 监督搜阈值，不符合这轮“靠近 DeepLog 式无监督”的试验目标。

### 影响模块
- benchmarks/models/my_model_public_unsupervised.py
- benchmarks/runners/run_hdfs_my_model_protocol_unsupervised.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已具备与原 benchmark 逻辑并行存在的独立无监督三视图试验入口。
- HDFS 首轮无监督试验已跑通，但固定 train-quantile 阈值下 fusion 的 recall 极低，说明这版虽然更无监督，但阈值/校准仍需继续调。

### 编码检查
- `python -m py_compile` 已通过：
  - `benchmarks/models/my_model_public_unsupervised.py`
  - `benchmarks/runners/run_hdfs_my_model_protocol_unsupervised.py`

### Git 状态
- 待提交

## 2026-04-24 无监督三视图阈值策略最小修复

### 修改内容
- 更新 `benchmarks/models/my_model_public_unsupervised.py` 的阈值选择逻辑：当 `val` 集存在且标签可用时，不再强制使用 `train q=0.95`，而是优先对 fusion 分数执行 `val_f1_search`。
- 仅保留 `train quantile` 作为无 `val` 标签时的后备路径，不改动该版本的三路 train-percentile 校准与等权融合定义。

### 修改原因
- 用户要求先修“最开始那一版 + HDFS 全量 normal train”，而当前主要故障点已确认是 fusion 最后一层阈值，不是三路分数本身。
- 采用最小改动可直接验证：在不重写分支与融合规则的前提下，仅更换阈值策略能否解除 fusion 被压死的问题。

### 影响模块
- benchmarks/models/my_model_public_unsupervised.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前修复目标是保持该独立版的 train-percentile 三视图结构不变，只替换最终 fusion 阈值选择方式。
- full-train HDFS 首次重跑时发现 train 集一次性构造 `334933 x 128` 序列矩阵会触发内存分配失败，因此进一步将该独立版的 scoring 改为按 chunk 分批打分。
- 实际指标需以本轮 HDFS full-train 重跑结果为准。

### 编码检查
- 待本轮 `py_compile` 与重跑验证

### Git 状态
- 待提交

## 2026-04-24 公共基准实验论文定位说明

### 修改内容
- 新增 `reports/final_thesis_package/public_benchmark_positioning_20260424.md`，集中整理公共基准实验在论文中的定位、与 DeepLog 的对比写法、主实验/补充实验分层结构，以及当前 HDFS/BGL 结果应如何表述。

### 修改原因
- 用户已确认论文主线不再押在 public benchmark 上，需要形成可直接用于论文实验章节与答辩说明的统一叙事口径。
- 当前仓库已积累多轮 HDFS/BGL protocol-aligned 结果，但若不先明确“哪些结果是主结论、哪些结果是补充验证”，后续章节写作容易继续混乱。

### 影响模块
- reports/final_thesis_package/public_benchmark_positioning_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已形成可直接服务于论文第 5 章和答辩表述的公共基准定位说明文稿。
- 后续可在此基础上继续拆分为正式正文段落、表格说明与讨论章节内容。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-24 公共基准结果快照整理

### 修改内容
- 新增 `reports/final_thesis_package/public_benchmark_snapshot_20260424.md`，集中收口当前 HDFS/BGL protocol-aligned benchmark 的关键结果、对比结论和论文可用表述。
- 在同一文件中统一整理了：HDFS 原始 full-train 无监督三视图、阈值修复版、DeepLog temporal residual 版，以及 BGL full multi-view 版的关键指标。

### 修改原因
- 用户希望我主动找点事情做，因此将当前分散在多轮实验中的结果收口为一份可直接引用的快照，减少后续论文写作时反复翻找 JSON 的成本。
- 当前 public benchmark 结果已经足够支撑“补充验证”叙事，需要一个统一载体承接这些结论。

### 影响模块
- reports/final_thesis_package/public_benchmark_snapshot_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已形成一份一页式 benchmark 快照，可直接服务于论文第 5 章写作、结果表筛选与答辩口径整理。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-24 公共基准正文草稿补写

### 修改内容
- 新增 `reports/final_thesis_package/chapter5_public_benchmark_draft_20260424.md`，将当前 public benchmark 的核心结论整理为可直接并入论文第 5 章的正文草稿。
- 草稿中已按论文口径区分：HDFS 的 temporal 主导结论、BGL 的 semantic 主导结论，以及 public benchmark 作为“补充验证而非主结论支柱”的整体定位。

### 修改原因
- 用户要求我主动持续推进工作，因此将前面形成的结果快照进一步转写为可直接服务于论文写作的正文版文稿，减少后续从结果到文本的手工转换成本。

### 影响模块
- reports/final_thesis_package/chapter5_public_benchmark_draft_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已形成一版可直接裁剪进论文第 5 章的公共基准实验正文草稿。
- 后续可在此基础上继续压缩成最终成稿版本或拆分为表格说明与讨论段落。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-24 公共基准表格与图注草稿补写

### 修改内容
- 新增 `reports/final_thesis_package/public_benchmark_tables_20260424.md`，将当前 HDFS/BGL public benchmark 结果整理为可直接转表的 Markdown 表格、推荐表注与图注草稿。
- 文档中同步给出：正文应保留的表格版本、应放补充实验的结果，以及写作时应避免的高风险表述。

### 修改原因
- 用户要求我持续主动推进，因此在正文草稿基础上进一步补齐“可直接落版”的表格与图注材料，减少后续人工整理成本。

### 影响模块
- reports/final_thesis_package/public_benchmark_tables_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已形成 public benchmark 的正文草稿、结果快照与表格图注三件套材料，可直接支撑论文第 5 章的写作与排版。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-24 公共基准终稿插入版补写

### 修改内容
- 新增 `reports/final_thesis_package/chapter5_public_benchmark_final_insert_20260424.md`，将公共基准定位、HDFS/BGL 结果解释、正文小结与表格放置建议压缩为更适合直接并入论文第 5 章的终稿插入版。

### 修改原因
- 当前仓库中已经有定位说明、结果快照、正文草稿和表格图注草稿，但仍缺少一份更短、更适合直接落版到论文正文中的压缩版本。
- 用户要求持续主动推进，因此补齐一份“可直接贴入章节”的最终版材料，减少后续再手工压缩的成本。

### 影响模块
- reports/final_thesis_package/chapter5_public_benchmark_final_insert_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 public benchmark 相关论文材料已形成定位说明、结果快照、正文草稿、表格图注草稿和终稿插入版五件套，可直接支撑第 5 章写作与排版。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-24 公共基准答辩口径稿补写

### 修改内容
- 新增 `reports/final_thesis_package/public_benchmark_defense_notes_20260424.md`，整理 public benchmark 在答辩中的一句话定位、常见追问、推荐回答与应避免的高风险表述。

### 修改原因
- 当前仓库中已经形成论文正文版材料，但仍缺少一份更偏答辩表达、可直接口头复述的压缩口径稿。
- 用户要求持续主动推进，因此补齐一份面向答辩场景的公共基准说明文稿，减少后续现场组织语言的成本。

### 影响模块
- reports/final_thesis_package/public_benchmark_defense_notes_20260424.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 public benchmark 相关材料已进一步扩展为包含答辩口径版本，可同时服务于正文撰写与现场答辩表达。

### 编码检查
- Markdown 文件已按 UTF-8 写入

### Git 状态
- 待提交

## 2026-04-23 三视图接入 DeepLog 风格时序分支独立试验

### 修改内容
- 新增 `benchmarks/models/my_model_public_deeplog_temporal.py`，在三视图 benchmark 适配器中保留 statistical / semantic 分支，但将 temporal 分支替换为 `benchmarks/models/temporal_public.py` 的 DeepLog 风格 next-event scorer。
- 新版本继续使用 train-normal percentile 校准，但 temporal 原始分数不再来自 `ThreeViewScoringService` 内部的 Bi-LSTM 校准分，而是来自独立训练的 `temporal_public` scorer。
- 新增 `benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal.py`，用于单独运行 HDFS 的 DeepLog-temporal 三视图对照版本。

### 修改原因
- 用户明确要求新开一个独立版本，并指出“按道理起码时序都应该和 DeepLog 一样”。
- 上一版无监督三视图虽然改成了 train-normal 校准，但 temporal 分支仍取自 `three_view_service.py` 的 Bi-LSTM/proxy 混合打分，不等同于 DeepLog 风格时序异常分，因此需要单独替换分支本体。

### 影响模块
- benchmarks/models/my_model_public_deeplog_temporal.py
- benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已具备“stat + semantic 保持不变、temporal 改为 DeepLog 风格 scorer”的独立试验入口。
- 实际指标需以本轮 HDFS 小样本重跑结果为准。

### 编码检查
- `python -m py_compile` 已通过：
  - `benchmarks/models/my_model_public_deeplog_temporal.py`
  - `benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal.py`

### Git 状态
- 待提交

## 2026-04-23 DeepLog temporal 主导的 residual 三视图试验

### 修改内容
- 新增 `benchmarks/models/my_model_public_deeplog_temporal_residual.py`，以 DeepLog 风格 temporal score 作为主分，statistical / semantic 仅作为小权重 residual 加成，不再对三路做等权 percentile 均值融合。
- 新增 `benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal_residual.py`，用于在相同 HDFS protocol 下直接对比 residual 融合版本。
- residual 版本默认通过 `val` 搜索融合阈值，并在输出中同时保留 temporal 自身阈值与 residual 融合阈值，便于区分“时序本体是否正常”和“融合后是否受损”。

### 修改原因
- 上一版实验已经确认 DeepLog temporal 本身有效，但 train-quantile 的三路等权融合阈值会把 fusion 直接压死。
- 用户要求按“DeepLog temporal 为主分，stat/semantic 只做小权重 residual 融合”的思路再跑一次。

### 影响模块
- benchmarks/models/my_model_public_deeplog_temporal_residual.py
- benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal_residual.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已具备 temporal 主导、stat/semantic 仅做辅助加成的独立试验入口。
- 实际指标需以本轮 HDFS residual 重跑结果为准。

### 编码检查
- `python -m py_compile` 已通过：
  - `benchmarks/models/my_model_public_deeplog_temporal_residual.py`
  - `benchmarks/runners/run_hdfs_my_model_protocol_deeplog_temporal_residual.py`

### Git 状态
- 待提交

## 2026-04-22 HDFS 公共基准协议修复

### 修改内容
- 将 `benchmarks/models/temporal_public.py` 从单类 BCE 监督分类改为 normal-only 的 next-event prediction 时序异常检测，实现基于 `top-k miss ratio` 的序列异常分数。
- 重写 `benchmarks/models/semantic_public.py` 的状态输出逻辑，新增 `mode / backend / fallback` 日志；当 `semantic_public_template` 实际回退到 hash 时，不再将其当作正式 template 结果解释，并输出 `invalid_due_to_hash_fallback`。
- 将 HDFS 的 `benchmarks/models/fusion_public.py` 改为合法 score fusion，新增 `fusion_public_mean` 与 `fusion_public_weighted`，权重和阈值仅在 `val` 上选择，`test` 只做最终评估。
- 重写 `benchmarks/runners/run_hdfs_public.py` 的结果表结构，新增 `Status` 与 `Notes` 字段，移除 strict normal-only HDFS 下不合法的 supervision-based `fusion_public` 汇报。
- 新增 `reports/hdfs_public_benchmark_analysis.md`，记录本轮 HDFS 协议修复、审计结论与正式可用结果。
- 更新 `README_public_benchmarks.md`，同步当前 HDFS 公共基准的真实实现口径与结果表字段规范。

### 修改原因
- 原始 `temporal_public` 在 normal-only HDFS 训练协议下使用单类 BCE，导致分支退化，结果不可用。
- 原始 `semantic_public_template` 在模型加载失败后会回退到 hash，但旧表格仍把它当作正式 template 结果汇报，语义口径不准确。
- 原始 HDFS `fusion_public` 依赖监督式 XGBoost，不适用于 strict normal-only 训练约束，需要改为合法的 score fusion。
- 需要让 HDFS 公共基准结果能够以明确状态字段和审计结论的方式进入论文与答辩材料，而不是继续沿用旧口径高分或无效结果。

### 影响模块
- benchmarks/models/temporal_public.py
- benchmarks/models/semantic_public.py
- benchmarks/models/fusion_public.py
- benchmarks/runners/run_hdfs_public.py
- README_public_benchmarks.md
- reports/hdfs_public_benchmark_analysis.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- HDFS leakage audit 当前已通过。
- 当前正式可用的 HDFS 结果包括：`temporal_public`、`semantic_public_hash`、`statistical_public`、`fusion_public_mean`、`fusion_public_weighted`。
- `semantic_public_template` 当前保留但状态为 `invalid_due_to_hash_fallback`，不得解释为真正的 template embedding 结果。
- strict normal-only HDFS 下不再汇报 supervision-based `fusion_public`。

### 编码检查
- benchmarks/models/temporal_public.py 已通过 `py_compile`
- benchmarks/models/semantic_public.py 已通过 `py_compile`
- benchmarks/models/fusion_public.py 已通过 `py_compile`
- benchmarks/runners/run_hdfs_public.py 已通过 `py_compile`
- README_public_benchmarks.md 已通过 UTF-8 回读
- reports/hdfs_public_benchmark_analysis.md 已通过 UTF-8 写入

### Git 状态
- 待提交


## 2026-04-22

### 修改内容
- 新增 `reports/thesis_narrative_outline.md`，整理论文整体叙事、实验章节结构与 public benchmark 的推荐写法
- 明确 AID 仍为论文主线，HDFS/BGL 定位为 protocol-aligned 的补充验证而非 strict reproduction

### 修改原因
- 用户在公开基准结果出来后对论文主线与实验章节表述出现混乱，需要形成可直接改写进论文的结构化文稿

### 影响模块
- reports/thesis_narrative_outline.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已给出可直接用于摘要、实验设计、结果分析与讨论章节的表述模板
- 明确区分主实验证据与公开基准补充验证的角色

### 编码检查
- 未额外执行

### Git 状态
- 未提交


## 2026-04-22

### 修改内容
- 补充 BGL public benchmark 的协议审计元数据，在 `run_bgl_public.py` 输出中写入排序、切分、train 过滤、语义输入模式与时序打分模式
- 为 `temporal_public` 增加 BGL 对照版 sequence-level score：`temporal_public_bgl_sequence`
- 为 `semantic_public` 显式记录 `input_mode=template_sequence_text`
- 新增 `reports/bgl_protocol_alignment_report.md`，整理当前实现与 DeepLog / LogBERT 公开协议的对照关系
- 更新 `README_public_benchmarks.md`，同步 BGL 当前真实协议口径与新增说明字段

### 修改原因
- 用户要求核查 BGL 是否严格按既定顺序处理，并把 temporal score、semantic 输入与协议对齐状态固化为可审计输出与论文文档

### 影响模块
- benchmarks/models/temporal_public.py
- benchmarks/models/semantic_public.py
- benchmarks/runners/run_bgl_public.py
- reports/bgl_protocol_alignment_report.md
- README_public_benchmarks.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- BGL 结果文件现在可以直接说明样本构造与切分协议
- 新增的 `temporal_public_bgl_sequence` 仅作为 BGL 对照项，不改变原正式 fusion 口径
- HDFS 流程未改动

### 编码检查
- 待执行 py_compile / runner 验证

### Git 状态
- 未提交


## 2026-04-22

### 修改内容
- 新增 `reports/public_benchmark_thesis_sections.md`，整理公开基准补充实验在论文第 4 章实验设计与第 5 章结果分析中的正式写法
- 明确 HDFS / BGL 在论文中的定位为 protocol-aligned supplementary evaluation，而非 strict reproduction

### 修改原因
- 用户希望在 benchmark 长时间运行期间先推进论文写作，需要可直接改写进正文的正式文稿

### 影响模块
- reports/public_benchmark_thesis_sections.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已形成可直接用于论文实验章节的完整中文段落
- 明确区分主线 AID、主实验、公开基准补充验证与文献参考对照

### 编码检查
- 未额外执行

### Git 状态
- 未提交


## 2026-04-22

### 修改内容
- 新增 `reports/thesis_discussion_and_limitations.md`，补充摘要口径、讨论、局限性分析、威胁分析与未来工作写法

### 修改原因
- 用户希望优先推进论文写作，在 benchmark 长时间运行期间补齐可直接改写进正文的讨论与局限性内容

### 影响模块
- reports/thesis_discussion_and_limitations.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已形成可直接用于摘要、讨论、局限性与威胁分析章节的中文段落
- 明确 public benchmark 的定位为补充验证而非严格复现

### 编码检查
- 未额外执行

### Git 状态
- 未提交


## 2026-04-22

### 修改内容
- 新增 `reports/thesis_conclusion_chapter.md`，补充论文结论与展望章节的完整正文草稿

### 修改原因
- 用户要求继续推进论文写作，需要形成可直接改写进最终论文的结论章节内容

### 影响模块
- reports/thesis_conclusion_chapter.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已形成覆盖研究总结、主要结论、不足反思与未来展望的结论章节正文
- 与前面形成的实验设计、结果分析和讨论稿保持同一叙事口径

### 编码检查
- 未额外执行

### Git 状态
- 未提交


## 2026-04-22

### 修改内容
- 新增 `reports/thesis_abstract_and_intro.md`，补充中文摘要、引言开头、研究问题、主要工作与创新点草稿

### 修改原因
- 用户要求继续推进论文写作，需要形成与前面实验章节和结论章节一致的摘要与引言口径

### 影响模块
- reports/thesis_abstract_and_intro.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已形成与 AID 主线、主实验主证据、public benchmark 补充验证相一致的摘要与引言表述
- 可直接用于论文开头部分改写

### 编码检查
- 未额外执行

### Git 状态
- 未提交


## 2026-04-23

### 修改内容
- 重构 `benchmarks/models/temporal_public.py`，拆分出 `train_temporal_public_model()` 与 `score_temporal_public()`
- 更新 `benchmarks/runners/run_bgl_public.py`，使 BGL 对照分数复用同一套 temporal 模型，不再重复训练第二遍

### 修改原因
- 之前为 BGL 新增 sequence-level 对照分数时，错误地重复训练了一次 temporal 模型，导致单次验证耗时异常增加

### 影响模块
- benchmarks/models/temporal_public.py
- benchmarks/runners/run_bgl_public.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 BGL 可在单次 temporal 训练后输出正式 `mean_miss_ratio` 与对照 `sequence_miss_burst_ratio`
- 结果口径不变，但运行效率显著改善

### 编码检查
- 已执行 `python -m py_compile` 语法检查

### Git 状态
- 未提交


## 2026-04-23

### 修改内容
- 为 BGL 新增 `semantic_public_raw`，使用去噪后的 raw event/message sequence text 作为语义输入
- 新增 `fusion_bgl_stat_semraw`，用于诊断统计分支与 raw semantic 结合后是否优于纯 statistical_public
- 新增 `bgl_semantic_raw_audit.json`，记录 raw semantic 输入模式、阈值来源以及相对 template semantic / statistical_public 的对照结果
- 更新 `README_public_benchmarks.md` 与 `reports/bgl_protocol_alignment_report.md`，同步 raw semantic 诊断口径

### 修改原因
- 用户要求优先验证 BGL 的主要瓶颈是否来自 template-level 语义信息不足，而不是继续在 temporal aggregation 或大范围 fusion 上试错

### 影响模块
- benchmarks/models/semantic_public.py
- benchmarks/models/fusion_public.py
- benchmarks/runners/run_bgl_public.py
- README_public_benchmarks.md
- reports/bgl_protocol_alignment_report.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 BGL 在保持原协议不变的前提下，已可输出 template semantic、raw semantic 与 stat+semraw 诊断性融合结果
- 可直接通过 audit 判断 raw semantic 是否优于 template semantic，以及 stat+semraw 是否超过 statistical_public

### 编码检查
- 待执行 py_compile / runner 验证

### Git 状态
- 未提交

## 2026-04-23 BGL temporal 全面调参汇总脚本

### 修改内容
- 新增 `scripts/run_bgl_temporal_tuning.py`，固定 `deeplog_true_prob_topk_mean` 为主线 scorer，对 `aggregate_k / temporal_top_k / temporal_window_size / epochs` 做两阶段加一轮 epoch 补扫。
- 脚本直接复用 `train_temporal_public_model(...)` 与 `score_temporal_public(...)`，不再把本轮验证重新引向 semantic 或 fusion。
- 新增正式产物输出：phase A / phase B / phase C CSV、总排名 summary CSV / JSON，以及 `reports/bgl_temporal_tuning_summary_<timestamp>.md`。
- 汇总排序规则固定为 `F1 desc -> PR-AUC desc -> Recall desc`，并在 summary 中直接给出 best config、top-5 和相对旧 best (`F1=0.2311`) 的增量。

### 修改原因
- 用户要求不要再做零散小试，而是对 temporal 视图做更系统的小样本调参，并给出一份可直接判断最佳组合的汇总结果。
- 之前的 runner 仍会混入 semantic / fusion 日志，不利于把本轮优化焦点严格收敛在 temporal 视图上。

### 影响模块
- scripts/run_bgl_temporal_tuning.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- BGL temporal 小样本 sweep 现在可以独立运行，并稳定生成阶段结果与最终排名汇总文件。
- 后续是否触发全量重跑，可直接依据 summary 文件中的最佳组合与旧 best 差值判断。

### 编码检查
- 已执行 `python -m py_compile scripts/run_bgl_temporal_tuning.py`
- 待执行 `python scripts/run_bgl_temporal_tuning.py`

### Git 状态
- 待提交

## 2026-04-23 BGL temporal DeepLog 对齐

### 修改内容
- 将 `benchmarks/models/temporal_public.py` 的主 backbone 收敛到 `NextEventModel`，默认可切换 `lstm`，并优先采用 `models.deeplog.*` 的默认维度。
- 新增 DeepLog 风格 score mode：`deeplog_topk_miss_ratio` 与 `deeplog_topk_miss_count`，把 step-level top-k miss 作为主判定方式。
- 在 `benchmarks/runners/run_bgl_public.py` 中新增正式结果行 `temporal_public_bgl_deeplog_topk_miss`，并在 JSON 中记录对应 score mode。
- 在 `benchmarks/configs/bgl.yaml` 中加入 `benchmarks.public_logs.temporal_rnn_type: lstm` 默认项。

### 修改原因
- 用户要求尽可能让 BGL temporal 的处理思路同步经典 DeepLog，而不是继续停留在概率均值聚合式 scoring。
- 需要把当前 public benchmark 的时序分支与 `src/models/train_deeplog.py` 的处理链尽量对齐，便于解释和对照。

### 影响模块
- benchmarks/models/temporal_public.py
- benchmarks/runners/run_bgl_public.py
- benchmarks/configs/bgl.yaml
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前 BGL temporal 已经新增更经典的 top-k miss 判定口径，可与原有 `deeplog_true_prob_topk_mean` 直接并排比较。
- 已将 HDFS / BGL 两条 public temporal 配置入口统一到 `temporal_rnn_type: lstm`，避免两套 benchmark 在 backbone 上继续漂移。
- 代码级语法检查已通过，focused 验证正在进行中。

### 编码检查
- 已执行 `python -m py_compile benchmarks/models/temporal_public.py`
- 已执行 `python -m py_compile benchmarks/runners/run_bgl_public.py`
- focused 验证进行中

### Git 状态
- 待提交

## 2026-04-23 论文对齐版 DeepLog runner

### 修改内容
- 新增 `benchmarks/runners/_deeplog_protocol_common.py`，封装论文对齐版 DeepLog 的 LSTM 训练、`top-g + r` 判分与标准化输出。
- 新增 `benchmarks/runners/run_hdfs_deeplog_protocol.py`，按 `Drain + session ID(BlockId) + normal-only 5000` 运行 HDFS DeepLog 协议。
- 新增 `benchmarks/runners/run_bgl_deeplog_protocol.py`，按 `Drain + 5-minute window + normal-only 5000` 运行 BGL DeepLog 协议。
- 将 `benchmarks/configs/bgl.yaml` 的训练 normal sequence 上限调到 `5000`，并把 `stride_minutes` 调整为 `5`，使 BGL 更接近论文描述的 5 分钟窗口径。
- 在两条论文对齐 runner 中显式锁定 `temporal_rnn_type=lstm`，避免再次漂回 GRU。

### 修改原因
- 用户明确要求按 LogBERT 表 2 所引用的 DeepLog/LogAnomaly 协议重做 HDFS / BGL，而不是继续沿用仓库现有 public benchmark 的解释框架。
- 需要把 parser、sequence construction、normal-only 训练规模和 `top-g + r` 判分方式统一到论文描述本身。

### 影响模块
- benchmarks/runners/_deeplog_protocol_common.py
- benchmarks/runners/run_hdfs_deeplog_protocol.py
- benchmarks/runners/run_bgl_deeplog_protocol.py
- benchmarks/configs/bgl.yaml
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前已生成两条独立的论文对齐版 DeepLog runner，保持与旧 public benchmark runner 分离。
- 代码级语法检查已通过，HDFS / BGL 论文对齐版运行中。

### 编码检查
- 已执行 `python -m py_compile benchmarks/runners/_deeplog_protocol_common.py`
- 已执行 `python -m py_compile benchmarks/runners/run_hdfs_deeplog_protocol.py`
- 已执行 `python -m py_compile benchmarks/runners/run_bgl_deeplog_protocol.py`
- HDFS / BGL runner 正在运行

### Git 状态
- 待提交

## 2026-04-25 AIT-LDS v2 full-data 截断时序协议支持

### 修改内容
- 为 `src/data_processing/truncated_protocol.py` 的 `build_truncated_ordered_splits(...)` 增加 `full_data` 参数。
- 在 `full_data=True` 时保持 `truncated_ordered_pre_split_v1` 的截断比例、时序切分比例、阈值选择和协议字段不变，仅将 train/val/test 的有效样本上限改为各 split 可构造的全部滑动窗口数。
- 为 `scripts/run_truncated_ordered_split.py` 增加 `--full-data` 与 `--datasets` 参数。
- full-data 运行结果写入 `outputs/reports/full_data_truncated_ordered/`，模型写入 `outputs/strict_retrain/truncated_ordered_protocol_full_data/`，避免覆盖既有 capped 论文主线结果。
- 在结果行、summary 与 manifest 中记录 `sample_cap_mode`、configured/effective sample caps 与实际 split sequence 数，便于区分 capped run 与 full-data run。

### 修改原因
- 用户需要在 AIT-LDS v2 主线中补充“与 `truncated_ordered_pre_split_v1` 参数一致，但不再限制 `24000/6000/6000` 样本上限”的 full-data 实验结果。
- 原默认配置适合受控论文主表复现，但不能直接代表 full-data 结果。

### 影响模块
- src/data_processing/truncated_protocol.py
- scripts/run_truncated_ordered_split.py
- reports/final_thesis_package/ait_lds_v2_full_data_truncated_results_20260425.md
- outputs/reports/full_data_truncated_ordered/
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已完成 `python scripts/run_truncated_ordered_split.py --full-data` 三子集重跑，输出主结果：`outputs/reports/full_data_truncated_ordered/view_eval_truncated_ordered_pre_split_full_data_20260425_121432.csv`。
- full-data 样本规模：harrison=`167256/41777/69662`，santos=`115404/35475/26595`，fox=`83835/27913/27913`。
- full-data 最佳 F1：harrison=`0.8442`，santos=`0.9326`，fox=`0.7483`。
- 新增结果报告：`reports/final_thesis_package/ait_lds_v2_full_data_truncated_results_20260425.md`。
- 默认不带 `--full-data` 的 capped 运行行为保持不变。

### 编码检查
- 已执行 `python -m py_compile src/data_processing/truncated_protocol.py scripts/run_truncated_ordered_split.py`
- 已执行 `python scripts/run_truncated_ordered_split.py --help`

### Git 状态
- 待提交

## 2026-04-25 AIT-LDS v2 统一 60/20/20 full-data 截断切分试验

### 修改内容
- 扩展 `build_truncated_ordered_splits(...)`，支持通过 `ratio_override` 覆盖 train/val 比例，并用 `split_variant` 记录切分变体。
- 为 `scripts/run_truncated_ordered_split.py` 增加 `--uniform-split-60-20-20` 参数，可在保持各数据集 trunc_ratio 不变的前提下统一使用 `60% / 20% / 20%` 时序切分。
- 统一切分 full-data 输出写入 `outputs/reports/full_data_truncated_ordered_uniform_60_20_20/`，模型写入 `outputs/strict_retrain/truncated_ordered_protocol_full_data_uniform_60_20_20/`。
- 新增结果报告 `reports/final_thesis_package/ait_lds_v2_uniform_60_20_20_full_data_results_20260425.md`。

### 修改原因
- 用户希望验证更规整的统一 `60/20/20` 截断时序切分是否能作为当前 dataset-specific 切分的替代或补充。

### 影响模块
- src/data_processing/truncated_protocol.py
- scripts/run_truncated_ordered_split.py
- reports/final_thesis_package/ait_lds_v2_uniform_60_20_20_full_data_results_20260425.md
- outputs/reports/full_data_truncated_ordered_uniform_60_20_20/
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已完成 `python scripts/run_truncated_ordered_split.py --full-data --uniform-split-60-20-20` 三子集重跑。
- 主结果表：`outputs/reports/full_data_truncated_ordered_uniform_60_20_20/view_eval_truncated_ordered_pre_split_full_data_uniform_60_20_20_20260425_123543.csv`。
- 统一 `60/20/20` full-data 最佳 F1：harrison=`0.8035`，santos=`0.9496`，fox=`0.7483`。
- 该方案更规整，适合作为鲁棒性补充；但 harrison 表现低于 dataset-specific full-data，因此暂不建议直接替代主线。

### 编码检查
- 已执行 `python -m py_compile src/data_processing/truncated_protocol.py scripts/run_truncated_ordered_split.py`
- 已执行 `python scripts/run_truncated_ordered_split.py --help`

### Git 状态
- 待提交

## 2026-04-25 AIT-LDS v2 full-data 截断切分候选比例支持

### 修改内容
- 为 `scripts/run_truncated_ordered_split.py` 增加 `--split-ratio` 参数，支持 `dataset_specific`、`60/20/20`、`60/15/25`、`65/20/15`、`65/15/20`。
- 保留 `--uniform-split-60-20-20` 兼容入口，内部映射到 `60/20/20`。
- 将 full-data 候选比例输出按 `split_variant` 区分到独立 report/model 目录，避免不同候选实验产物混淆。
- 保持 `truncated_ordered_pre_split_v1` 协议 ID 不变，仅通过 `split_variant` 与比例 metadata 记录切分变体。

### 修改原因
- 用户需要试验 `60/15/25`、`65/20/15`、`65/15/20` 三组统一候选切分，用于比较 val/test 大小变化对异常比例与指标稳定性的影响。

### 影响模块
- scripts/run_truncated_ordered_split.py
- outputs/reports/full_data_truncated_ordered_*/
- outputs/strict_retrain/truncated_ordered_protocol_full_data_*/
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已完成三组候选 full-data 实验：`60/15/25`、`65/20/15`、`65/15/20`。
- 主结果分别写入 `outputs/reports/full_data_truncated_ordered_uniform_60_15_25/`、`outputs/reports/full_data_truncated_ordered_uniform_65_20_15/`、`outputs/reports/full_data_truncated_ordered_uniform_65_15_20/`。
- 候选对比报告：`reports/final_thesis_package/ait_lds_v2_candidate_split_sensitivity_20260425.md`。
- 综合结果显示 `65/15/20` 的 Macro-F1 最高，为 `0.9055`，最低子集 F1 为 `0.8309`，是本轮候选中最均衡的统一切分方案。
- 新增 `65/15/20` 主路线完整表：`reports/final_thesis_package/table_65_15_20_all_views_20260425.md` 与 `reports/final_thesis_package/table_65_15_20_core_views_20260425.md`；其中 `gru_temporal_view` 明确归为时序基线，不作为 AIT-LDS v2 核心视图。

### 编码检查
- 已执行 `python -m py_compile scripts/run_truncated_ordered_split.py src/data_processing/truncated_protocol.py`
- 已执行 `python scripts/run_truncated_ordered_split.py --help`

### Git 状态
- 待提交

## 2026-04-25 AIT-LDS v2 论文出版级图表生成

### 修改内容
- 新增 `scripts/build_publication_thesis_figures_20260425.py`，基于 `full_data + truncated_ordered_pre_split_v1 + uniform_65_15_20` 主线生成学术简洁风格静态图。
- 新增 `reports/final_thesis_package/figures_publication_20260425/`，输出 7 张论文图，每张包含 PNG、SVG、PDF 三种格式。
- 新增 `reports/final_thesis_package/publication_figures_manifest_20260425.json`，记录图表数据源、协议字段、输出路径和风格信息。
- 新增 `reports/final_thesis_package/chapter5_figure_placement_plan_20260425.md` 与 `reports/final_thesis_package/chapter5_figure_captions_20260425.md`，用于第 5 章图表放置和图题说明。

### 修改原因
- 用户希望论文图表更美观，尤其需要可直接放入论文正文的高分辨率静态图，并切换到当前 `65/15/20` 实验主路线。

### 影响模块
- scripts/build_publication_thesis_figures_20260425.py
- reports/final_thesis_package/figures_publication_20260425/
- reports/final_thesis_package/publication_figures_manifest_20260425.json
- reports/final_thesis_package/chapter5_figure_placement_plan_20260425.md
- reports/final_thesis_package/chapter5_figure_captions_20260425.md
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 已生成 7 张出版级论文图，共 21 个文件：PNG/SVG/PDF 各 7 个。
- 图表覆盖切分敏感性、异常比例分布、协议对比、核心模型热力图、融合变体、最佳模型指标平衡和时序基线对比。
- 修正图 5-3、图 5-6、图 5-7 等图的图例和数值标签遮挡问题，将图例移出绘图区并跳过零值伪标签。
- 图 5-6 最佳模型 Precision / Recall / F1 平衡图改为竖向分组柱状图，图例置于图外下方，并将数值标签横向显示在柱顶，避免遮挡。

### 编码检查
- 已执行 `python scripts/build_publication_thesis_figures_20260425.py`
- 已执行 `python -m py_compile scripts/build_publication_thesis_figures_20260425.py`
- 已校验 manifest 输出路径均存在，PNG 文件均可打开。

### Git 状态
- 待提交

## 2026-04-25 前端论文演示界面改版

### 修改内容
- 新增前端未上传日志时的 AIT-LDS v2 演示首页，突出多视图检测、XGBoost 融合、事件分析和 RAG + AI 辅助研判能力。
- 简化侧边栏 AI 配置展示，将服务类型、模型名称、Base URL、API Key 收纳到“AI 服务高级配置”折叠面板。
- 将工作台入口中的“技术分析”调整为“模型解释”，“模型与规则管理”调整为“配置管理”。
- 优化检测结果总览 hero 文案，明确统计、时序、语义三视图与融合模型的论文主线口径。
- 将模型解释页标题与说明改为多视图模型解释口径，并兼容旧的“技术分析”路由名称。

### 修改原因
- 用户准备进入论文答辩/演示阶段，需要前端从工具型界面调整为更适合展示 AIT-LDS v2 方法贡献和演示流程的界面。

### 影响模块
- frontend/app.py
- frontend/helpers.py
- frontend/panels.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 前端首屏在未上传日志时会展示系统能力和演示流程。
- 检测后总览与模型解释页面更贴合论文叙事，但不改变检测、RAG、AI 报告和导出逻辑。

### 编码检查
- 已执行 `python -m py_compile frontend/app.py frontend/helpers.py frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 AI 分析输出截断修复

### 修改内容
- 为 `AIJudge` 增加 `qa_max_tokens` 与 `report_max_tokens`，区分普通问答和事件分析报告的输出长度上限。
- 将事件分析报告生成从通用 `max_tokens` 改为报告专用上限，避免 8 段式报告生成到一半被截断。
- 将 AI 问答生成从通用 `max_tokens` 改为问答专用上限，并在模型因长度上限停止时追加提示。
- 更新前端运行态配置解析，确保 profile 中的 `qa_max_tokens` 与 `report_max_tokens` 能正确传入 AI Judge。
- 在事件报告生成设置中展示当前报告输出上限，便于确认运行配置。
- 将默认 AI profile 的 `request_timeout` 提高到 90 秒，并配置 `qa_max_tokens=1000`、`report_max_tokens=3000`。

### 修改原因
- 用户反馈进行 AI 分析时内容未生成完整就被截断，根因是当前 AI Judge 默认输出上限偏低，事件报告临时上限也不足以稳定生成完整中文报告。

### 影响模块
- src/rag/ai_judge.py
- frontend/runtime.py
- frontend/panels.py
- configs/config.yaml
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 事件分析报告现在使用更高的报告专用输出上限，普通 AI 问答也使用独立上限。
- 如果模型仍因长度限制停止，页面会在输出末尾显示明确提示，而不是静默截断。

### 编码检查
- 已执行 `python -m py_compile src/rag/ai_judge.py frontend/runtime.py frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 配置管理页 UI 与 Profile 逻辑整理

### 修改内容
- 将配置页标题统一为“配置管理”，并重排为状态卡片、当前生效配置、Profile 管理、编辑当前 Profile、测试与保存几个清晰区块。
- 将当前生效配置改为默认收起的折叠区域，减少页面首屏信息噪音。
- 将新增 Profile 放入单独折叠区，按钮改为“从当前 Profile 复制新增”，避免与编辑、删除、保存操作混淆。
- Profile 表格新增 QA 输出上限、事件报告输出上限、Timeout 等字段，便于诊断 AI 输出截断问题。
- 编辑当前 Profile 时新增生成参数区，支持配置 temperature、批量判断上限、AI 问答输出上限、事件报告输出上限和请求超时。
- 补全配置管理页的 profile 规范化、表单读取和保存逻辑，保存 YAML 时不再丢失 `qa_max_tokens` 与 `report_max_tokens`。

### 修改原因
- 用户反馈模型与规则管理界面 UI 和添加逻辑混乱，需要整理为更适合演示和维护的配置管理中心。

### 影响模块
- frontend/panels.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 配置管理页的操作顺序更清晰，Profile 新增、默认切换、删除、重载、编辑、测试和保存职责更明确。
- AI 问答和事件报告输出上限可直接在前端查看和修改。

### 编码检查
- 已执行 `python -m py_compile frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 配置管理默认 Profile 生效修复

### 修改内容
- 调整侧边栏 AI 配置逻辑，新增已保存 Profile 下拉选择，可在侧边栏直接切换 `default`、`kimi` 等已保存模型配置。
- 将高级配置中的覆盖开关改为“临时覆盖当前 Profile”，默认不再用侧边栏手填字段覆盖配置管理中保存的 Profile。
- 调整前端运行态 AI 配置解析，仅在临时覆盖开启时才使用侧边栏 provider、model、base_url、api_key。
- 将 AI 问答输出上限统一提升到 `qa_max_tokens=3000`，事件报告输出上限统一提升到 `report_max_tokens=8000`。
- 同步更新配置管理页、运行态快照和 AIJudge 默认值，避免保存后上限回落。

### 修改原因
- 用户反馈配置管理中设置默认模型后不生效，只有侧边栏改参数才有效；根因是侧边栏参数始终优先覆盖了已保存 Profile。
- 用户反馈 AI 回答仍存在截断，需要进一步提高问答和报告的独立输出上限。

### 影响模块
- frontend/app.py
- frontend/runtime.py
- frontend/panels.py
- src/rag/ai_judge.py
- configs/config.yaml
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 侧边栏现在可以直接选择已保存 Profile 作为本次会话使用的 AI 模型配置。
- 配置管理中保存的默认 Profile 仍作为首次进入页面时的默认选项。
- 侧边栏手填参数只作为显式临时调试覆盖，不再干扰持久化默认模型。
- AI 问答和事件报告具备更高输出上限，仍触发长度限制时会显示明确提示。

### 编码检查
- 已执行 `python -m py_compile frontend/app.py frontend/runtime.py frontend/panels.py src/rag/ai_judge.py`

### Git 状态
- 待提交

## 2026-04-25 事件分析筛选布局优化

### 修改内容
- 将事件分析页的风险等级、事件类型、关键词搜索和排序方式筛选控件从侧边栏移入“事件队列”顶部。
- 将事件筛选区改为默认收起的折叠面板，减少左侧首屏占用。
- 为事件队列增加最大高度和内部滚动，避免事件数量较多时拉长整页。
- 将事件详情顶部的关联告警数、最高风险分、主要分类三张指标卡改为容器内紧凑网格，避免 Streamlit 三列布局撑出外层边框。
- 将筛选命中数量显示移动到事件队列区域内。
- 更新空结果提示文案，引导用户调整事件队列上方筛选条件。

### 修改原因
- 事件筛选与事件队列属于同一操作流程，放在主内容区顶部比放在全局侧边栏更直观，也减少侧边栏与 AI Profile 配置的职责混杂。

### 影响模块
- frontend/panels.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 事件分析页左侧形成“筛选条件 → 命中数量 → 事件队列”的连续操作链路，同时默认只展示队列本体。
- 左侧事件队列过长时在区域内滚动，右侧事件详情不会被左侧列表显著拉长。
- 侧边栏保留全局工作台、检测参数和 AI Profile 选择，不再承载事件队列内部筛选。

### 编码检查
- 已执行 `python -m py_compile frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 前端通用日志平台文案调整

### 修改内容
- 去除前端首页和检测结果总览中的 `AIT-LDS v2 演示系统` 文案。
- 将首页定位调整为“多源日志智能分析平台”，强调适配安全、系统与服务日志。
- 将结果总览中的 `RAG 辅助研判` 文案改为更通用的“相似案例辅助”。

### 修改原因
- 前端不应只面向单一数据集或特定 AIT 展示场景，需要呈现为通用日志异常检测与事件研判系统。

### 影响模块
- frontend/app.py
- frontend/helpers.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 前端 Hero 文案从特定演示系统口径调整为通用多源日志分析平台口径。
- 已确认 `frontend/*.py` 中不再出现 `AIT-LDS` 和 `演示系统` 字样。

### 编码检查
- 已执行 `python -m py_compile frontend/app.py frontend/helpers.py frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 大盘告警集中度替换分数相关性

### 修改内容
- 将安全态势大盘中的“分数相关性”热力图替换为“告警集中度”模块。
- 新增 Top 10% 风险贡献、最长连续告警、分布判断三个集中度指标。
- 新增按序列窗口聚合的告警数柱状图与平均风险折线图，用于观察风险是否集中爆发。

### 修改原因
- 分数相关性更偏实验分析，前端大盘参考价值有限；告警集中度更能回答当前风险是零散异常还是局部/高度集中爆发。

### 影响模块
- frontend/panels.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 大盘新增风险聚集程度视角，与已有安全分类构成和多视图主导来源不重复。
- 该改动只替换相关性展示区域，未改变检测、分类、事件聚合和模型逻辑。

### 编码检查
- 已执行 `python -m py_compile frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-25 当前事件详情 UI 优化

### 修改内容
- 将当前事件详情顶部重组为事件摘要卡，突出风险等级、主分类、最高风险、摘要、时间范围、影响范围和关键实体。
- 将建议动作从结论正文中拆成独立的强调卡片。
- 将下方三张指标卡调整为关联告警数、平均风险分、主导视图，减少与顶部最高风险和主分类的重复。
- 删除“融合诊断”页内重复的建议动作卡片，避免同一建议在详情页中重复出现。

### 修改原因
- 当前事件详情需要更像 triage 摘要，先给结论与处置建议，再展示补充指标和证据，减少信息堆叠。

### 影响模块
- frontend/panels.py
- FUNCTION_UPDATE_LOG.md

### 结果说明
- 当前事件详情顶部信息层级更清晰，结论、建议、指标、解释和证据分区更明确。
- 未改变事件聚合、RAG 检索、AI 报告和检测结果逻辑。

### 编码检查
- 已执行 `python -m py_compile frontend/panels.py`

### Git 状态
- 待提交

## 2026-04-29

### 修改内容
- 为 RAG 检索增加高置信证据门控，区分 `high` 证据与 `candidate` 候选参考。
- 默认关闭无过阈值时强制返回 Top-1 的兜底逻辑，避免低质量案例误导事件结论。
- 前端运行时只允许高置信 RAG 回填辅助分类和建议，并且只允许“其他可疑行为”被 RAG 升级。
- 事件分析页和 RAG 面板区分“高置信案例证据”和“候选参考”，候选参考不进入 AI 主证据。
- LLM 事件报告和问答上下文只接收通过门控的 `rag_cases`，无高置信案例时要求说明案例证据不足。

### 修改原因
- 当前 RAG 案例库规模和语义表示质量有限，低置信相似案例可能把事件解释和 LLM 研判带偏。
- 需要明确 RAG 与检测主链路的边界：RAG 只做辅助研判，高置信才可作为报告证据。

### 影响模块
- `src/rag/attack_case_base.py`
- `configs/config.yaml`
- `frontend/runtime.py`
- `frontend/panels.py`
- `src/rag/ai_judge.py`

### 结果说明
- 低置信 RAG 仍可在前端作为人工候选参考查看，但不会改写主分类，也不会进入 LLM 主证据。
- 高置信判断同时要求向量相似度与重排排序分达标，降低仅靠关键词 boost 造成的误报风险。

### 编码检查
- `python -m py_compile src/rag/attack_case_base.py frontend/runtime.py frontend/panels.py src/rag/ai_judge.py` 已通过。

### Git 状态
- 未提交

## 2026-04-29 RAG 自动扩库增强

### 修改内容
- 将 `russellmitchell` 纳入默认 RAG 自动扩充数据集，训练后 `--with-rag` 与单独 `--build-rag` 均会覆盖该子集。
- 为 `AUTO-*` 自动案例补充结构化元数据：`dataset`、`template_id`、`template_count`、`label_source`、`review_status`、`case_origin`、`quality_gate`。
- 接线 `rag.case_base.incremental_append`，支持累计扩库与仅基于默认案例+本轮自动案例的可控重建。
- 增强 RAG 构建日志，输出各数据集新增案例数、总新增数、索引重建状态和最终索引规模。
- 前端 RAG 检索结果和事件级案例卡片展示案例来源、审核状态、来源数据集与模板计数。
- 旧版 `AUTO-*` 历史案例归一化时补齐 `dataset`、`template_id`、`quality_gate` 等结构化键。

### 修改原因
- RAG 案例库需要从已标注异常模板中更系统地扩充，同时避免自动案例来源不清、质量不可追溯。
- 自动案例元数据有助于论文说明、前端演示和后续人工审核。

### 影响模块
- `configs/config.yaml`
- `main.py`
- `src/rag/attack_case_base.py`
- `frontend/panels.py`
- `FUNCTION_UPDATE_LOG.md`

### 结果说明
- RAG 自动扩库覆盖面扩大到 `fox/harrison/santos/russellmitchell`。
- 自动案例仍需通过现有模板质量、频次、领域 hint 和去重门控；检索阶段继续受高置信证据门控约束。
- `python main.py --build-rag --rag-force` 已完成，索引重建成功，当前案例总数 48，AUTO 案例 15。
- 自动案例元数据抽样检查通过，全部 AUTO 案例均包含新增结构化键。

### 编码检查
- `python -m py_compile main.py src/rag/attack_case_base.py frontend/panels.py` 已通过。

### Git 状态
- 未提交

## 2026-04-29 完整训练构建执行

### 执行内容
- 执行 `python main.py --all --train-mode all --with-rag --rag-force` 完成 Harrison 主配置训练。
- 继续使用 `LOG_DATASET=fox` 与 `LOG_DATASET=santos` 补跑另外两个 AIT-LDS v2 子数据集。
- 每个数据集均完成日志解析、特征提取、Bi-LSTM 训练、Isolation Forest 训练、XGBoost 融合训练。
- 训练后执行 RAG 自动扩库与索引重建。

### 结果说明
- Harrison：precision=0.9788，recall=0.9086，f1=0.9424，auc=0.9960。
- Fox：precision=0.9252，recall=0.6222，f1=0.7440，auc=0.9547。
- Santos：precision=0.9120，recall=0.9222，f1=0.9171，auc=0.9875。
- 解析输出覆盖 `data/processed/harrison/harrison_parsed.csv`、`data/processed/fox/fox_parsed.csv`、`data/processed/santos/santos_parsed.csv`。
- 模型输出更新：`models/bilstm/best_model.pth`、`models/isolation_forest/iforest_model.joblib`、`models/xgboost/xgboost_fusion.joblib`。
- RAG 自动扩库覆盖 `fox/harrison/santos/russellmitchell`，本轮新增 0 条，索引总数 48。
- 已确认关键训练产物和 RAG 文件均存在。

### Git 状态
- 未提交

## 2026-04-29 RAG 案例库实际扩展

### 修改内容
- 将 `rag.case_base.auto_case_require_security_or_system_hint` 调整为 `false`，允许已标注异常且模板质量合格的非显式安全关键词模板进入待审核自动案例。
- 自动案例 `quality_gate` 记录 `domain_hint_ok` 或 `domain_hint_relaxed`，区分强领域命中与放宽纳入。

### 修改原因
- 原策略领域 hint 门控过严，多个数据集可用异常模板被过滤，导致 RAG 自动扩库连续新增 0 条。
- 放宽后仍保留标签、频次、模板质量、去重与待审核状态，降低误扩风险。

### 结果说明
- 执行 `python main.py --build-rag --rag-force` 后新增 12 条 AUTO 案例。
- 检查重复后发现 8 条低价值 `metricbeat/system.cpu` 泛化案例，已从案例库移除。
- 扩库规则新增 relaxed 来源白名单，仅允许 Apache、auth、audit、OpenVPN、dnsmasq 等来源在未命中领域关键词时进入待审核案例。
- 清理后 RAG 案例库为 52 条，其中 AUTO 案例 19 条，索引已按 52 条重建。
- 复查结果：无 case_id 重复、无模板精确重复，仅剩 2 组 DNS/登录会话跨数据集近重复，保留用于跨数据集覆盖。

### 编码检查
- `python -m py_compile src/rag/attack_case_base.py` 已通过。

### Git 状态
- 未提交

## 2026-04-29 高质量 RAG 内置案例扩展

### 修改内容
- 新增 15 条高质量内置安全案例，覆盖 WebShell、命令注入、恶意下载、C2 信标、数据外传、横向移动、SSH 密钥篡改、cron/systemd 持久化、凭据发现、日志篡改、归档暂存、路径穿越、VPN 凭据滥用、DNS 隧道、容器/服务账号滥用等场景。
- 所有新增案例均补充 MITRE 风格 technique、英文检索内容和中文处置建议。

### 修改原因
- 原 RAG 库在 Credential Access、Initial Access、Discovery 上覆盖较多，但对攻击链中后段的 Persistence、C2、Exfiltration、Lateral Movement、Defense Evasion 覆盖不足。
- 高质量内置案例比泛化自动案例更适合作为 LLM 研判时的稳定证据来源。

### 结果说明
- 执行 `python main.py --build-rag --rag-force` 后，RAG 案例库从 52 条扩展到 67 条。
- 当前内置案例 48 条，AUTO 案例 19 条。
- 重复检查通过：无 case_id 重复、无模板精确重复；仅保留 2 组跨数据集近重复 AUTO 案例。
- RAG 索引 `data/vectors/rag_attack_cases.npz` 已按 67 条案例重建。

### 编码检查
- `python -m py_compile src/rag/attack_case_base.py` 已通过。

### Git 状态
- 未提交

## 2026-04-29 论文第 5 章实验部分补全稿

### 修改内容
- 参考 `lunwen.docx` 当前第 5 章结构，生成完整实验章节补全稿。
- 补全实验目标、实验环境、数据集划分、单视图实验、多视图融合、消融实验、切分敏感性、DeepLog 对比、公开基准补充验证、RAG 案例库分析和本章小结。
- 整理并写入主实验表格、最佳模型表、消融表、切分对比表、DeepLog 对比表、公共基准表和 RAG 案例库构成表。

### 输出文件
- `reports/final_thesis_package/chapter5_complete_experiment_section_for_lunwen_20260429.md`
- `reports/final_thesis_package/chapter5_complete_experiment_section_for_lunwen_20260429.docx`

### 数据来源
- `lunwen.docx`
- `outputs/reports/full_data_truncated_ordered_uniform_65_15_20/view_eval_truncated_ordered_pre_split_full_data_uniform_65_15_20_20260425_135427.csv`
- `reports/final_thesis_package/ait_lds_v2_candidate_split_sensitivity_20260425.md`
- `reports/final_thesis_package/table_deeplog_vs_mainline_all.md`
- `data/rag/attack_cases.jsonl`

### Git 状态
- 未提交

## 2026-04-29 论文验收前一致性检查报告

### 修改内容
- 基于 `lunwen.docx` 提取文本生成验收前一致性检查报告。
- 梳理英文摘要旧口径、第 3/5/6 章占位符、第 5 章未替换完整实验稿等问题。
- 给出摘要替换建议、第 5 章替换来源、RAG/Hash/公共基准等统一表述口径。

### 输出文件
- `reports/final_thesis_package/lunwen_precheck_consistency_report_20260429.md`

### 结果说明
- 当前 `lunwen.docx` 不建议直接提交验收，优先整改顺序为：修正摘要、替换第 5 章、清理全文 `【待补】`、补齐系统图与截图。
- 第 5 章建议直接使用 `chapter5_complete_experiment_section_for_lunwen_20260429.docx` 替换现有占位版章节。

### Git 状态
- 未提交

## 2026-04-29 论文修正版 Word 生成

### 修改内容
- 基于原始 `lunwen.docx` 生成不覆盖原文件的修正版 Word。
- 修正英文摘要中的旧 `Loghub benchmark dataset`、`F1-score of 0.958` 和 `edge-cloud collaborative deployment architecture` 口径。
- 将当前第 5 章占位版替换为完整实验章节，并规范第 5 章标题层级。

### 输出文件
- `reports/final_thesis_package/lunwen_revised_for_precheck_20260429.docx`
- `reports/final_thesis_package/lunwen_revised_for_precheck_extracted_text_20260429.txt`

### 验证结果
- 修正版文本中已无 `Loghub benchmark dataset`、`F1-score of 0.958`、`edge-cloud collaborative` 旧口径。
- 第 5 章已包含完整实验结构：单视图、融合、消融、切分敏感性、DeepLog 对比、公共日志数据集补充验证、RAG 案例库分析。
- 第 3 章和第 6 章仍保留若干 `【待补】` 占位符，后续需要继续清理方法图、参数说明和系统截图引用。

### Git 状态
- 未提交

## 2026-04-29 论文完整预检版生成

### 修改内容
- 基于 `lunwen_revised_for_precheck_20260429.docx` 生成完整预检版 Word。
- 清理第 3 章方法设计中的 `【待补】` 占位符，补齐固定窗口、统计特征、Bi-LSTM 参数、Hash 语义表示、融合输入和验证集阈值选择说明。
- 清理第 6 章系统实现中的 `【待补】` 占位符，将图片占位改为当前系统模块和流程文字描述，并按实际前端功能写明 `.txt`、`.md`、Markdown/HTML 导出能力。

### 输出文件
- `reports/final_thesis_package/lunwen_revised_full_precheck_20260429.docx`
- `reports/final_thesis_package/lunwen_revised_full_precheck_extracted_text_20260429.txt`

### 验证结果
- 完整预检版文本中已无 `待补`、`图【待补`、`表【待补`。
- 已无旧英文摘要口径：`Loghub benchmark dataset`、`F1-score of 0.958`、`edge-cloud`。
- 第 5 章标题层级正常，包含公共日志数据集补充验证与 RAG 案例库分析。

### Git 状态
- 未提交

## 2026-04-30 论文第 3.4 节语义视图优化稿

### 修改内容
- 根据当前代码实现重写论文第 3.4 节“语义视图设计”。
- 明确区分时序视图的可训练模板 ID embedding 与语义视图的哈希文本表示。
- 补齐日志文本清洗、哈希向量化、sentence-transformers 对照、风险锚点相似度与规则先验融合的正式论文表述。

### 输出文件
- `reports/final_thesis_package/chapter3_4_semantic_view_polished_20260430.md`

### 依据口径
- 当前主实验语义视图使用 `force_hash_fallback: true`，哈希回退实际维度为 256。
- 语义风险分由向量相似度与风险锚点计算，并融合轻量规则先验，不单独训练语义分类器。

### Git 状态
- 未提交

## 2026-05-01 统计视图窗口长度时间顺序协议复测

### 执行内容
- 在 Harrison 子集上基于 `truncated_ordered_pre_split` 协议顺序复测统计视图窗口长度 `20/30/50`。
- 固定基础窗口 `50`、时序窗口 `50`、hash 语义模式，使用 train=24000、val=6000、test=6000。
- 三组实验顺序运行，避免共享模型目录并行覆盖。

### 输出文件
- `outputs/reports/view_eval_truncated_ordered_pre_split_20260501_004901.csv`（统计窗口 20）
- `outputs/reports/view_eval_truncated_ordered_pre_split_20260501_004944.csv`（统计窗口 30）
- `outputs/reports/view_eval_truncated_ordered_pre_split_20260501_005025.csv`（统计窗口 50）
- `reports/final_thesis_package/statistical_window_length_truncated_ordered_harrison_20260501.md`

### 结果说明
- `xgboost_fusion_stat_parts_xgb` 在统计窗口 30 时取得最高 F1=0.9395，高于窗口 20 的 0.9241 和窗口 50 的 0.8268。
- 当前时间顺序协议下仍支持统计窗口取 30 的默认设置。

### Git 状态
- 未提交

## 2026-05-01 论文第 3.5 节融合机制优化稿

### 修改内容
- 根据当前 XGBoost 融合实现重写论文第 3.5 节与第 3.6 节小结。
- 补齐简单平均局限、XGBoost 选择原因、统计子分融合输入、交叉特征和验证集阈值选择说明。
- 统一当前融合输入口径：`stat/temp/sem` 与 `stat_dist/stat_auth/stat_web/stat_dns`。

### 输出文件
- `reports/final_thesis_package/chapter3_5_fusion_mechanism_polished_20260501.md`

### 依据口径
- 当前配置启用 `models.xgboost.use_stat_parts=true` 和 `include_legacy_stat_in_meta=true`。
- 评估阈值由验证集搜索最优 F1 得到，测试集不参与阈值选择。

### Git 状态
- 未提交

## 2026-05-01 论文第 4 章 RAG 与大模型研判增强优化稿

### 修改内容
- 根据当前项目 RAG 案例库、检索阈值、证据门控和 AI Judge 实现重写论文第 4 章。
- 明确 RAG 与大模型属于检测后研判增强层，不参与融合模型训练、阈值选择或基础检测指标计算。
- 补齐案例库构建、Top-3 相似案例检索、高置信证据与候选参考区分、LLM 结构化输出和规则回退机制表述。

### 输出文件
- `reports/final_thesis_package/chapter4_rag_llm_analysis_polished_20260501.md`

### 依据口径
- 当前 RAG 配置使用 `top_k=3`，并通过相似度、原始排序分和前端候选阈值区分证据可用性。
- 当前 AI Judge 支持大模型 JSON 研判输出，并在模型不可用时基于融合分数和多视图一致性进行规则回退。

### Git 状态
- 未提交

## 2026-05-01 论文第 5 章实验设计与结果分析优化稿

### 修改内容
- 基于现有主实验结果重写第 5 章“实验设计与结果分析”。
- 明确补充实验路线：数据准备、样本构造、单视图实验、融合实验、消融实验、协议与基线实验、RAG 研判增强分析。
- 用已有真实指标替换原稿中的待补项，包含主实验、最佳融合、消融、切分敏感性、DeepLog 基线、公共数据集和 RAG 案例库分析。

### 输出文件
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`

### 依据口径
- 主实验采用 AIT-LDS v2 full-data 截断时序协议，统一 `65% / 15% / 20%` 训练、验证、测试切分。
- 阈值由验证集搜索确定，测试集仅用于最终性能评估。
- RAG 与 AI Judge 作为检测后解释模块，不参与检测指标计算。

### Git 状态
- 未提交

## 2026-05-01 论文第 5 章实验结构调整

### 修改内容
- 根据论文主线调整第 5 章实验结构，弱化切分比例敏感性实验在正文中的位置。
- 将原 5.8 替换为 Hash 与 Embedding 语义表示对比实验，说明单视图与融合场景下的差异。
- 新增统计视图窗口长度影响实验，使用当前 `truncated_ordered_pre_split` 复测结果论证统计窗口长度 30 的设置。
- 扩展主流模型对比实验，增加 GRU temporal、Bi-LSTM + Attention temporal、DeepLog 与本文最佳融合模型的对比分析。

### 输出文件
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`

### 依据口径
- 语义表示对比引用 `table_semantic_mode_compare_20260420.md` 与 `semantic_mode_analysis_20260420.md`。
- 窗口长度实验引用 `statistical_window_length_truncated_ordered_harrison_20260501.md`。
- 主流模型对比引用主实验 CSV 中的 GRU temporal 结果和 DeepLog 对比表。
- 修正 Hash/Embedding 对比表述：融合行改为“同语义模式内最佳 XGBoost 融合”，并明确该表为早期补充实验口径，不与 `65% / 15% / 20%` 主实验最终指标混用。

### Git 状态
- 未提交

## 2026-05-01 语义表示主协议复测与第 5 章口径修正

### 修改内容
- 在 `65% / 15% / 20%` 主实验协议下分别重跑 Hash 与 Embedding 语义表示实验，统一使用 full-data、`truncated_ordered_pre_split`、验证集选阈值、测试集最终评估。
- 新增 Hash/Embedding 对比汇总 CSV 与 Markdown 报告，覆盖语义单视图、统计子分融合、统计子分+原统计分融合以及同语义模式内最佳模型对比。
- 更新论文第 5.8 节，将原早期补充实验口径替换为主协议复测结果：Embedding 在语义单视图上更强；融合后 harrison、santos 由 Hash 取得更高最优 F1，fox 由 Embedding 取得更高最优 F1。
- 更新论文第 5.10 节主流模型对比表述，将 GRU/Bi-LSTM + Attention 作为同输入时序分支比较，将 DeepLog 与完整多视图系统作为系统级补充对比，避免将不同输入信息量的模型简单等价比较。
- 更新第 5 章小结，明确语义表示选择具有数据集依赖性，完整系统优势主要来自统计、时序和语义异构证据融合。

### 输出文件
- `outputs/reports/full_data_truncated_ordered_uniform_65_15_20/view_eval_truncated_ordered_pre_split_full_data_uniform_65_15_20_20260501_170204.csv`
- `outputs/reports/full_data_truncated_ordered_uniform_65_15_20/view_eval_truncated_ordered_pre_split_full_data_uniform_65_15_20_20260501_171322.csv`
- `reports/final_thesis_package/semantic_mode_compare_uniform_65_15_20_20260501.csv`
- `reports/final_thesis_package/semantic_mode_compare_uniform_65_15_20_20260501.md`
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`

### 结果说明
- 同语义模式内最佳模型对比：harrison Hash F1=0.9382，Embedding F1=0.8328；santos Hash F1=0.9474，Embedding F1=0.8961；fox Hash F1=0.8309，Embedding F1=0.9024。
- 当前论文结论调整为：Embedding 更强于单独文本表达，Hash 在 harrison/santos 的融合场景中更稳定，Embedding 在 fox 场景下更优。
- DeepLog 对比仅作为系统级补充说明，不再表述为完全同输入条件下的公平模型结构对比。

### Git 状态
- 未提交

## 2026-05-01 论文监督式定位与引用评价口径调整

### 修改内容
- 将摘要、引言草稿、第 3 章方法稿和第 5 章实验稿统一调整为“面向有标注安全日志场景的监督式多视图风险识别与研判增强”口径。
- 明确 DeepLog、LogBERT 等经典方法属于无监督/自监督或序列建模范式参照，不作为唯一严格公平主对比对象。
- 在第 5 章中将“主流模型对比”改为“监督模型与经典范式对比”，区分同输入时序分支比较、融合策略比较和系统级补充比较。
- 新增“相关工作引用与本文评价口径补充稿”，说明仍可引用 DeepLog、LogBERT、LogRobust、NeuralLog、PLELog 等工作，但应按序列建模、语义建模、监督分类和研判增强四类组织。
- 补充本文评价标准：是否提升有标注安全日志风险识别效果、是否证明多视图互补、是否优于固定融合、是否具备解释和落地价值、是否清楚说明适用边界。

### 输出文件
- `reports/final_thesis_package/abstract_refresh_20260420.md`
- `reports/thesis_abstract_and_intro.md`
- `reports/final_thesis_package/chapter3_1_framework_polished_20260430.md`
- `reports/final_thesis_package/chapter3_2_statistical_view_polished_20260430.md`
- `reports/final_thesis_package/chapter3_3_temporal_attention_polished_20260430.md`
- `reports/final_thesis_package/chapter3_4_semantic_view_polished_20260430.md`
- `reports/final_thesis_package/chapter3_5_fusion_mechanism_polished_20260501.md`
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`
- `reports/final_thesis_package/related_work_positioning_and_evaluation_20260501.md`

### 结果说明
- 当前论文主线从“通用无监督日志异常检测”收敛为“有标注安全日志监督式风险识别”。
- 相关工作仍可引用经典日志异常检测论文，但引用目的调整为方法脉络和范式参照。
- 本文工作好坏主要通过监督式主实验、消融实验、融合策略对比和研判增强可用性评价，而不是简单对标所有无监督 SOTA。

### Git 状态
- 未提交

## 2026-05-01 监督式融合基线脚本与第 5 章对比表补充

### 修改内容
- 新增 `scripts/run_supervised_fusion_baselines.py`，在 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 主协议下运行监督式融合基线。
- 基线覆盖 Mean Fusion、Logistic Regression Fusion、Linear SVM Fusion、Random Forest Fusion、Extra Trees Fusion、Gradient Boosting Fusion 与 XGBoost Fusion。
- 监督融合输入统一为统计、时序、语义三视图风险分，以及分布、认证、Web、DNS 四类统计子分数。
- 生成三数据集合并版监督融合基线 CSV 与 Markdown 报告。
- 更新论文第 5.10 节，新增“不同监督式融合器对比结果”表，并顺延后续表号。

### 输出文件
- `scripts/run_supervised_fusion_baselines.py`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260501_183458.csv`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260501_183949.csv`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260501_183949_combined.csv`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260501_183949_combined.md`
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`

### 结果说明
- harrison 上 XGBoost Fusion 最优，F1=0.9382。
- santos 上 XGBoost Fusion 最优，F1=0.9474。
- fox 主实验最佳 XGBoost 配置仍为“统计子分数”，F1=0.8309；补充监督融合器基线中 Random Forest Fusion 达到 F1=0.8920。
- 结果支持“学习型监督融合显著优于简单平均”的结论；传统监督融合器表应作为公平主对比，说明多视图融合框架有效，同时指出不同数据集的最优融合分类器存在差异。

### Git 状态
- 未提交

## 2026-05-01 跨数据集融合层迁移实验

### 修改内容
- 新增 `scripts/run_cross_dataset_fusion_transfer.py`，用于运行融合层跨数据集迁移实验。
- 完成两组迁移：`harrison+santos → fox` 与 `harrison+fox → santos`。
- 迁移口径为源数据集训练融合层、源数据集验证集选择阈值、目标数据集测试集最终评估。
- 生成迁移实验 CSV 与 Markdown 报告，并在报告中补充结论说明。

### 输出文件
- `scripts/run_cross_dataset_fusion_transfer.py`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260501_193430.csv`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260501_193430.md`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260501_194519.csv`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260501_194519.md`

### 结果说明
- 已将本文主模型的三个 XGBoost 迁移变体纳入实验：三视图基础 XGBoost、统计子分数 XGBoost、统计子分数+原统计分 XGBoost。
- `harrison+santos → fox` 迁移效果较弱，本文最佳 XGBoost 变体为“统计子分数+原统计分”，F1=0.4408；统计子分数 XGBoost 为 0.4349，三视图基础 XGBoost 为 0.2734。
- `harrison+fox → santos` 迁移效果较好，本文最佳 XGBoost 变体为“统计子分数”，F1=0.9053；统计子分数+原统计分 XGBoost 为 0.9023，三视图基础 XGBoost 为 0.8520。
- 该实验说明统计子分数相比仅使用三视图分数具有更强跨场景表达能力，但跨数据集融合判定边界仍存在明显差异，尤其 fox 迁移难度较高。

### Git 状态
- 未提交

## 2026-05-01 XGBoost 小样本召回调参实验

### 修改内容
- 新增 `scripts/run_xgboost_recall_tuning_small_sample.py`，用于在小样本 cap 模式下测试 XGBoost 融合层召回率调参。
- 在 fox 小样本上测试 `scale_pos_weight` 放大 1.2、1.5、2.0，降低 `reg_lambda/gamma/min_child_weight`，增加 `max_depth` 及组合变体。
- 生成调参结果 CSV 与 Markdown 报告。
- 扩展脚本支持 `--full-data`，用于在全量样本下复测同一组类别权重和正则调参变体；修正 full-data 与 split-ratio 解析误绑定问题，确保全量复测使用 `65% / 15% / 20%`。

### 输出文件
- `scripts/run_xgboost_recall_tuning_small_sample.py`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_195748.csv`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_195748.md`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_200135.csv`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_200135.md`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_200659.csv`
- `reports/final_thesis_package/xgboost_recall_tuning_small_sample_uniform_65_15_20_20260501_200659.md`
- `reports/final_thesis_package/xgboost_recall_tuning_full_data_uniform_65_15_20_20260501_203429.csv`
- `reports/final_thesis_package/xgboost_recall_tuning_full_data_uniform_65_15_20_20260501_203429.md`

### 结果说明
- 已补充本文主模型口径测试：`stat_parts` 与 `stat_parts_plus_legacy` 两种特征集合分别调参，并在 harrison、santos、fox 三个数据集上复测。
- fox 小样本上，`stat_parts` 默认 XGBoost 达到 Precision=0.8359、Recall=0.8836、F1=0.8591；`scale_pos_weight×1.2` 后达到 Precision=0.8436、Recall=0.8830、F1=0.8628。
- harrison 上 `stat_parts_plus_legacy` 明显优于 `stat_parts`，默认配置达到 Precision=0.9836、Recall=0.8711、F1=0.9240；说明该数据集仍需要原统计总分参与融合。
- santos 上两种口径接近，`stat_parts` 最佳 F1=0.9430，`stat_parts_plus_legacy` 最佳 F1=0.9413，统计子分数拆分有效但原统计分不会明显损害性能。
- 三数据集小样本结果说明调参不具有简单全局普适性：统计子分数拆分具有跨数据集价值，但是否保留原统计总分应按验证集选择；类别权重与正则调参主要带来小幅、数据集相关收益。
- 全量样本 `65% / 15% / 20%` 复测中，harrison 的 `stat_parts_plus_legacy` 从默认 F1=0.9226 提升到 0.9456，主要来自 `max_depth=8 + 降低正则`。
- 全量 santos 调参收益很小：`stat_parts` 从 F1=0.9471 提升到 0.9497，`stat_parts_plus_legacy` 从 F1=0.9444 提升到 0.9457。
- 全量 fox 主模型口径 `stat_parts` 从 F1=0.8336 提升到 0.8353，仅小幅提升；`stat_parts_plus_legacy` 可由 F1=0.7570 提升到 0.8402，说明调参主要对较难特征口径有补救作用。

### Git 状态
- 未提交

## 2026-05-02 监督融合器公平扩展实验与第5章修正

### 修改内容
- 扩展 `scripts/run_supervised_fusion_baselines.py`，使 LR、Linear SVM、Random Forest、Extra Trees、Gradient Boosting 与 XGBoost 同时测试 `stat_parts` 和 `stat_parts_plus_legacy` 两种融合输入口径。
- 在 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 协议下重跑 harrison、santos、fox 三数据集监督融合器对比。
- 更新第 5 章实验叙述，将表 5-5 定位为“最佳 XGBoost 融合配置”，将表 5-10 更新为包含两种特征口径的监督融合器公平对比。
- 更新实验梳理文档，明确 fox 上 Random Forest 优势不是由只测试 `stat_parts_plus_legacy` 造成的。

### 输出文件
- `scripts/run_supervised_fusion_baselines.py`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260502_002936.csv`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260502_002936.md`
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`
- `reports/final_thesis_package/experiment_result_positioning_summary_20260501.md`

### 结果说明
- harrison 上仍由 `xgboost_fusion_stat_parts_plus_legacy` 最优，F1=0.9382。
- santos 上仍由 `xgboost_fusion_stat_parts_plus_legacy` 最优，F1=0.9474。
- fox 上 `random_forest_fusion_stat_parts_plus_legacy` 最优，F1=0.8920；`random_forest_fusion_stat_parts` 也达到 F1=0.8915，均高于 `xgboost_fusion_stat_parts` 的 F1=0.8309。
- 结论修正为：多视图监督融合框架有效，XGBoost 是 harrison/santos 上最优且整体稳定的主实现，但 fox 的最佳融合器为 Random Forest，说明融合器选择具有数据集依赖性。

### Git 状态
- 未提交

### 修改内容
- 新增论文实验体系梳理文档，统一整理主实验、监督式融合器对比、XGBoost 调参、小样本/全量样本差异和迁移实验的写作定位。
- 明确论文主线应表述为“多视图风险特征 + 监督式融合框架”，而不是“单一 XGBoost 分类器在所有数据集上最优”。
- 补充 fox 上 Random Forest Fusion 优于 XGBoost 的论文解释口径，以及答辩时可用的问题回答。

### 输出文件
- `reports/final_thesis_package/experiment_result_positioning_summary_20260501.md`

### 结果说明
- 建议将监督式融合器 full-data 对比作为主对比实验：harrison 与 santos 上 XGBoost Fusion 最优，fox 上 Random Forest Fusion 最优。
- 建议将 XGBoost 调参写作参数敏感性分析：full-data 下调参局部有效，但贡献小于特征口径和融合器选择。
- 建议将小样本调参放在附录或补充说明，不作为最终主性能排序依据。

### Git 状态
- 未提交

## 2026-05-03 第5章监督式融合基线对比重写

### 修改内容
- 重写 `chapter5_experiment_design_results_polished_20260501.md` 的实验目标、实验路线、5.6 融合分析、5.10 监督模型对比和本章小结相关表述。
- 将第 5.10 节改为以监督式融合基线为主对比，压缩 DeepLog 系统级补充对比篇幅。
- 统一论文结论口径：贡献落在多视图风险特征与监督式融合框架，而不是声称单一 XGBoost 在所有日志域绝对最优。

### 输出文件
- `reports/final_thesis_package/chapter5_experiment_design_results_polished_20260501.md`

### 结果说明
- harrison、santos 仍表述为 XGBoost Fusion 最优。
- fox 明确表述为 Random Forest Fusion 最优，F1=0.8920。
- 保留 XGBoost 作为默认主实现，但将监督式融合器选择差异写成数据集依赖性结论。

### Git 状态
- 未提交

## 2026-05-03 第5章实验思路与答辩策略文档

### 修改内容
- 新增第5章实验取舍与答辩策略文档，梳理正文应保留的主实验、监督式融合基线、消融、语义表示、窗口长度、公共数据集和 RAG 研判实验。
- 明确哪些结果应作为正文主表，哪些结果适合作为补充或附录。
- 补充答辩问题话术，覆盖 fox 上 Random Forest 优于 XGBoost、DeepLog 对比公平性、RAG 研判定位等问题。

### 输出文件
- `reports/final_thesis_package/chapter5_experiment_strategy_for_defense_20260503.md`

### 结果说明
- 建议第5章主线聚焦“多视图风险特征 + 监督式融合框架”。
- 建议正文必须保留单视图/Mean Fusion/默认 XGBoost、监督式融合器基线、消融和 RAG 案例库实验。
- 建议将小样本调参和过多参数组合放入附录或简述。

### Git 状态
- 未提交

## 2026-05-03 补充 santos+fox 到 harrison 迁移实验

### 修改内容
- 扩展 `scripts/run_cross_dataset_fusion_transfer.py`，新增 `santos+fox -> harrison` 迁移方向。
- 修复迁移脚本调用监督融合器规格函数时的参数兼容问题。
- 在 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 协议下重跑三组跨数据集融合层迁移实验。

### 输出文件
- `scripts/run_cross_dataset_fusion_transfer.py`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260503_155944.csv`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260503_155944.md`

### 结果说明
- `santos+fox -> harrison` 最佳模型为 `our_xgboost_stat_parts_plus_legacy_transfer`，Precision=0.9583，Recall=0.9771，F1=0.9676，PR-AUC=0.9924。
- 三组迁移最佳结果分别为：`harrison+santos -> fox` 的 Mean Fusion F1=0.5347，`harrison+fox -> santos` 的 Gradient Boosting F1=0.9234，`santos+fox -> harrison` 的 XGBoost 统计子分+原统计分 F1=0.9676。

### 编码检查
- `python -m py_compile scripts/run_cross_dataset_fusion_transfer.py` 通过。

### Git 状态
- 未提交

## 2026-05-03 迁移实验结果复跑核对

### 修改内容
- 按相同 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 协议复跑跨数据集融合层迁移实验。
- 核对前两组迁移方向 `harrison+santos -> fox` 与 `harrison+fox -> santos` 的结果稳定性。

### 输出文件
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260503_161801.csv`
- `reports/final_thesis_package/cross_dataset_fusion_transfer_uniform_65_15_20_20260503_161801.md`

### 结果说明
- 复跑结果与 `20260503_155944` 版本完全一致。
- `harrison+santos -> fox` 最佳仍为 Mean Fusion，F1=0.5347。
- `harrison+fox -> santos` 最佳仍为 Gradient Boosting Fusion，F1=0.9234。
- `santos+fox -> harrison` 最佳仍为 XGBoost 统计子分+原统计分，F1=0.9676。

### Git 状态
- 未提交

## 2026-05-03 原始三视图 XGBoost 与统计子分数 XGBoost 对比补跑

### 修改内容
- 扩展 `scripts/run_supervised_fusion_baselines.py`，新增 `base_3view` 特征口径，用于直接比较原始三视图 XGBoost 与统计子分数 XGBoost。
- 在 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 协议下重跑 harrison、santos、fox 三数据集监督式融合基线。

### 输出文件
- `scripts/run_supervised_fusion_baselines.py`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260503_171005.csv`
- `reports/final_thesis_package/supervised_fusion_baselines_uniform_65_15_20_20260503_171005.md`

### 结果说明
- 原始三视图 XGBoost F1：harrison=0.8165，santos=0.9261，fox=0.5902。
- 统计子分数 XGBoost F1：harrison=0.9171，santos=0.9468，fox=0.8309。
- 统计子分数+原统计分 XGBoost F1：harrison=0.9382，santos=0.9474，fox=0.7504。
- 结论：在当前主协议下，统计子分数口径相较原始三视图 XGBoost 在三数据集均提升 F1；是否额外保留原统计总分具有数据集依赖性。

### 编码检查
- `python -m py_compile scripts/run_supervised_fusion_baselines.py` 通过。

### Git 状态
- 未提交

## 2026-05-03 全新版第5章实验结构建议

### 修改内容
- 新增全新版第5章实验结构建议文档，按最新主协议数据重排章节结构、表格顺序和答辩口径。
- 将统计子分数拆分有效性实验提升为第5章重点小节。
- 将监督式融合器对比、跨数据集迁移实验、公共数据集补充验证和 RAG 研判增强重新定位。

### 输出文件
- `reports/final_thesis_package/chapter5_new_experiment_structure_20260503.md`

### 结果说明
- 建议第5章主线改为“多视图风险特征 + 统计子分数拆分 + 监督式融合框架 + RAG 研判增强”。
- 建议正文新增原始三视图 XGBoost 与统计子分数 XGBoost 对比表。
- 建议正文保留跨数据集迁移实验作为泛化性分析，并弱化 DeepLog 为系统级补充参照。

### Git 状态
- 未提交

## 2026-05-03 第5章 5.5 至 5.14 补充正文

### 修改内容
- 根据用户提供的第5章 5.5 以后草稿，补全并润色 5.5 至 5.14 的论文正文。
- 按最新 full-data、`truncated_ordered_pre_split`、`65% / 15% / 20%` 主协议结果重写实验叙述。
- 将原始三视图 XGBoost、统计子分数 XGBoost、监督式融合器对比、迁移实验、公共数据集补充验证和 RAG/AI Judge 研判实验分节展开。
- 修正“默认 XGBoost”与“原始三视图 XGBoost”口径混用问题，避免把 base_3view 指标与统计子分数融合指标混写。

### 输出文件
- `reports/final_thesis_package/chapter5_sections_5_5_to_5_14_complete_20260503.md`

### 结果说明
- 该补充稿覆盖第 5.5 至第 5.14 节，可作为后续整合进论文正文的基础版本。
- 论文主线收敛为“多视图风险特征 + 统计子分数拆分 + 监督式融合框架 + RAG/AI Judge 检测后研判增强”。
- 本次仅新增论文 Markdown 内容，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-03 典型高危事件研判示例表

### 修改内容
- 新增典型高危认证事件研判示例补充稿，用于论文中展示检测结果到 RAG/AI Judge 研判的闭环效果。
- 围绕 SSH 暴力破解或异常认证尝试场景，整理事件来源、风险等级、日志线索、多视图贡献、相似案例、AI Judge 结论和处置建议。
- 表格引用项目案例库中的 SSH brute force、SSH excessive login attempts、SSH account probing and user enumeration 等案例口径。

### 输出文件
- `reports/final_thesis_package/typical_high_risk_event_judgement_example_20260503.md`

### 结果说明
- 可作为第 5.13 节 RAG/AI Judge 研判增强实验后的案例展示内容。
- 该示例强调 RAG 与 AI Judge 只作为检测后解释增强，不参与检测指标计算。
- 本次仅新增论文 Markdown 内容，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文第6章系统实现重写

### 修改内容
- 根据当前项目实现重写第6章“系统实现与应用展示”。
- 按现有 Streamlit 前端工作台重构章节内容，覆盖安全态势大盘、事件分析、模型解释、相似案例检索、AI 安全助手和配置管理。
- 补充日志上传、序列构造、多视图打分、XGBoost 融合、事件聚合、RAG 检索、AI Judge 报告生成和导出流程。
- 将原“作战总览/高危定位/技术分析”等旧称统一为当前前端实际名称和功能口径。

### 输出文件
- `reports/final_thesis_package/chapter6_system_implementation_rewritten_20260504.md`

### 结果说明
- 新版第6章更贴合当前项目代码和前端界面，可作为论文系统实现章节基础稿。
- 明确 RAG 与 AI Judge 为检测后研判增强层，不改变检测主链路和指标计算。
- 本次仅新增论文 Markdown 内容，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文第7章总结与展望完善

### 修改内容
- 根据最新第5章实验结论和第6章系统实现口径，重写第7章“总结与展望”。
- 更新工作总结，覆盖多视图风险特征、统计子分数拆分、监督式融合、迁移实验、RAG/AI Judge 和系统原型实现。
- 更新主要结论，避免继续使用旧版过期指标，并明确 XGBoost 并非所有数据集绝对最优。
- 补充不足与未来工作，覆盖真实生产数据、跨场景迁移、语义建模、案例库质量、AI Judge 可信度和系统工程化。

### 输出文件
- `reports/final_thesis_package/chapter7_conclusion_and_future_work_rewritten_20260504.md`

### 结果说明
- 新版第7章与当前论文主线一致：多视图风险特征 + 统计子分数拆分 + 监督式融合框架 + RAG/AI Judge 研判增强。
- 结论中明确 harrison/santos 上 XGBoost 最优，fox 上 Random Forest 最优，避免过度声称单一分类器优势。
- 本次仅新增论文 Markdown 内容，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 第5至第7章最终整合稿

### 修改内容
- 新增第 5 至第 7 章最终整合 Markdown 稿。
- 使用旧版第 5 章 5.1 至 5.4 作为实验设计基础，接入新版第 5.5 至 5.14 最新实验分析。
- 整合第 6 章系统实现与第 7 章总结展望，并补充第 5 章到第 6 章、第 6 章到第 7 章的章节过渡文字。
- 将典型高危认证事件研判示例纳入第 5.13 节，统一编号为表 5-16。
- 统一第 5 章标题格式，并检查第 5、6、7 章表号和章节编号连续性。

### 输出文件
- `reports/final_thesis_package/chapters5_to_7_final_integrated_20260504.md`

### 结果说明
- 整合稿形成从实验验证、系统实现到总结展望的连续论文版本。
- 第 5 章保留最新口径：统计子分数拆分、监督式融合器对比、迁移实验、公共数据集补充验证和 RAG/AI Judge 检测后研判增强。
- 第 7 章继续明确 harrison/santos 上 XGBoost 最优、fox 上 Random Forest 最优，避免过度声称单一融合器绝对优势。
- 本次仅新增论文 Markdown 内容，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文图片插入位置分析

### 修改内容
- 阅读 `lunwen_260503.txt` 的章节结构和正文内容，分析全文适合插入图片的位置。
- 明确区分图片与表格，强调实验数据表不应截图成图。
- 按第 1 至第 7 章给出建议图片、插入位置、图片内容、必要性和可复用资源说明。
- 重点规划方法流程图、RAG/AI Judge 流程图、实验结果可视化图和系统界面截图。

### 输出文件
- `reports/final_thesis_package/lunwen_260503_figure_placement_plan_20260504.md`

### 结果说明
- 形成可直接用于后续画图和插入论文的图片需求清单。
- 建议全文使用 12 至 15 张核心图片，优先保留方法框架图、统计子分数结构图、RAG 研判流程图、关键实验 F1 对比图和系统界面截图。
- 本次仅新增论文辅助 Markdown 文档，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文核心图片生成

### 修改内容
- 新增论文图片生成脚本，批量生成方法流程图、RAG 研判流程图、实验 F1 对比图和系统架构图。
- 生成第 3 章多视图检测框架、日志预处理、统计子分数、Bi-LSTM Attention、语义哈希和融合判定流程图。
- 生成第 4 章 RAG/AI Judge 流程图和证据门控机制图。
- 生成第 5 章时间切分、单视图对比、统计子分数对比、监督式融合器对比、消融对比和典型事件证据链图。
- 生成第 6 章系统总体架构图，并输出配套图注清单和 manifest。

### 输出文件
- `reports/final_thesis_package/generate_lunwen_figures_20260504.py`
- `reports/final_thesis_package/figures_lunwen_20260504/`

### 结果说明
- 共生成 15 张论文核心图片，每张同时提供 PNG 和 SVG 格式。
- PNG 可直接插入 Word/WPS，SVG 可用于后续无损编辑或导出。
- 图注文件为 `reports/final_thesis_package/figures_lunwen_20260504/figure_captions_20260504.md`。
- 本次仅新增论文图片与生成脚本，不涉及代码主链路修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文删减与润色方案

### 修改内容
- 基于 `lunwen_260503.txt` 的章节结构和篇幅分布，整理全文删减与润色建议。
- 明确当前主稿属于“材料充分但篇幅偏长”的状态，建议最终版压缩到约 4 万至 4.8 万字符。
- 标出必须优先修正的问题，包括第 5 章标题编号混乱、占位语、错别字、表 5-6 缺少 F1 列和 WPS 临时公式图片路径。
- 按章节给出压缩比例、可删内容、不建议删除内容和推荐修改顺序。

### 输出文件
- `reports/final_thesis_package/lunwen_260503_reduction_polish_plan_20260504.md`

### 结果说明
- 该方案可作为后续精简正文、统一术语和修正格式问题的执行清单。
- 本次仅新增论文辅助 Markdown 文档，不涉及代码逻辑修改或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文图片学术化重绘

### 修改内容
- 调整论文图片生成脚本的全局输出目录，新增学术版图片目录，保留原始图片版本。
- 将图片风格改为更适合论文插图的低饱和配色、细边框、浅网格和克制版式。
- 将 PNG 输出提升到 300dpi，并设置 SVG 字体保留，便于后续无损编辑。
- 优化实验柱状图配色、纹理、网格线、坐标轴和图例位置，提高黑白打印和论文排版可读性。
- 修正学术版图注清单中图 5-2 至图 5-5 的编号标题。

### 输出文件
- `reports/final_thesis_package/generate_lunwen_figures_20260504.py`
- `reports/final_thesis_package/figures_lunwen_academic_20260504/`

### 结果说明
- 共重新生成 15 张学术风格论文图片，每张同时提供 PNG 和 SVG 格式。
- 原始图片目录 `figures_lunwen_20260504/` 未删除，可作为备份对照。
- 本次仅调整论文图片生成与图片资产，不涉及检测主链路或实验重跑。

### Git 状态
- 未提交

## 2026-05-04 论文图片 publication 结构化重画

### 修改内容
- 新增 publication 版论文图片生成脚本，重新设计图片结构，而不是仅调整颜色。
- 将总体框架图改为“检测主链路 + 研判增强链路”的分层结构图。
- 将日志预处理图改为时间轴滑动窗口表达，突出窗口标签和三视图样本对齐。
- 将统计视图图改为层次分解结构，展示统计特征到四类统计子分数的映射。
- 将 Bi-LSTM Attention 图改为模型结构图，展示模板序列、双向 LSTM、拼接状态、Attention 权重和时序分输出。
- 将 RAG 流程图改为泳道流程图，将证据门控图改为二维门控区域图。
- 将实验图从普通柱状图改为排序点图、连接点图和热力图，突出模型差异、提升轨迹和最优融合器。
- 新增正式图号映射，确保 manifest 和图注清单输出完整图号。

### 输出文件
- `reports/final_thesis_package/generate_lunwen_figures_publication_20260504.py`
- `reports/final_thesis_package/figures_lunwen_publication_20260504/`

### 结果说明
- 共生成 15 张 publication 结构化重画图片，每张同时提供 PNG 和 SVG 格式。
- 该版本相较原始版和 academic 版在图形表达结构上发生实质变化，更适合作为最终论文插图候选。
- 本次仅新增论文图片生成脚本和图片资产，不涉及检测主链路或实验重跑。

### Git 状态
- 未提交

## 2026-05-05 前端 XGBoost 推理切换为 CPU

### 修改内容
- 将 `configs/config.yaml` 中 `models.xgboost.use_gpu` 从 `true` 调整为 `false`。
- 前端演示场景下使用 CPU 进行 XGBoost 推理，避免模型在 `cuda:0` 而输入数据在 CPU 时触发 XGBoost DMatrix fallback 警告。

### 输出文件
- `configs/config.yaml`

### 结果说明
- 该调整优先保证前端演示稳定性和日志输出整洁性。
- 仅影响配置层面的 XGBoost 推理设备选择，不涉及模型训练结果重跑。

### Git 状态
- 未提交

## 2026-05-05 RAG 证据列类型转换警告修复

### 修改内容
- 修复 `frontend/runtime.py` 中合并 RAG 证据可用标记时的 Pandas FutureWarning。
- 将原先直接对 object 列执行 `fillna(False).astype(bool)` 后参与或运算的写法，拆分为显式布尔序列 `base_evidence` 和 `rag_evidence` 后再合并。

### 输出文件
- `frontend/runtime.py`

### 结果说明
- 消除点击事件分析或构建视图数据时可能出现的 `Downcasting object dtype arrays` 警告。
- 该修改不改变 RAG 证据合并逻辑，只明确类型转换过程。

### Git 状态
- 未提交

## 2026-05-05 前端事件分析按钮稳定性修复

### 修改内容
- 修复 `frontend/panels.py` 中事件分析队列按钮、复核按钮和导出按钮的状态管理方式。
- 将事件复核状态从 `set` 改为字符串列表，避免 Streamlit rerun 或序列化检查时遇到非稳定会话状态。
- 将包含模板原文和事件 ID 的动态长 widget key 改为短哈希 key，减少上传检测后点击按钮时的前端断连风险。
- 移除事件卡片选择和复核按钮中的强制 `st.rerun()`，改为依赖 Streamlit 默认按钮触发重跑。

### 输出文件
- `frontend/panels.py`

### 结果说明
- 上传日志并完成检测后，事件分析中的事件选择、标记复核和导出按钮不再把长模板文本或 set 对象写入按钮 key / session state。
- 已执行 `python -m py_compile frontend/panels.py`，语法检查通过。
- 未启动新的前端进程，避免影响用户正在运行的 Streamlit 实例。

### Git 状态
- 未提交

## 2026-05-05 RAG 证据布尔转换 FutureWarning 清除

### 修改内容
- 在 `frontend/runtime.py` 中新增 `_to_bool_series`，统一处理 RAG 证据列的布尔转换。
- 将 `RAG证据可用` 与 `RAG证据可用_rag` 的合并逻辑从 `fillna(False).astype(bool)` 改为逐值映射转换。
- 同步替换 `rag_ready_mask` 中的证据可用判断，避免同类 FutureWarning 再次出现。

### 输出文件
- `frontend/runtime.py`

### 结果说明
- 彻底避开 Pandas 对 object 列 `fillna(False)` 的 downcasting warning，降低前端按钮 rerun 后断连风险。
- 已执行 `python -m py_compile frontend/runtime.py`，语法检查通过。
- 未启动新的前端进程，避免影响用户正在运行的 Streamlit 实例。

### Git 状态
- 未提交

## 2026-05-05 前端演示日志文件截取

### 修改内容
- 从 `data/processed/harrison/harrison_parsed.csv` 的 `raw_log` 字段截取前 160 条原始日志。
- 生成可直接上传到 Streamlit 前端的轻量演示文件 `data/demo/harrison_frontend_demo_160.log`。
- 按前端演示需要追加生成约 500KB 的演示文件 `data/demo/harrison_frontend_demo_500kb.log`。
- 进一步生成约 2MB 的演示文件 `data/demo/harrison_frontend_demo_2mb.log`，用于展示更完整的事件队列和风险分布。

### 输出文件
- `data/demo/harrison_frontend_demo_160.log`
- `data/demo/harrison_frontend_demo_500kb.log`
- `data/demo/harrison_frontend_demo_2mb.log`

### 结果说明
- 轻量演示文件共 160 行，约 22 KB，适合快速验证上传检测流程。
- 500KB 演示文件共 2402 行，约 514 KB，适合用于常规前端展示。
- 2MB 演示文件共 15575 行，约 2.01 MB，适合用于完整前端展示、事件分析和截图演示。
- 文件内容保留原始时间戳和安全演练事件名称，不包含 CSV 表头或解析字段。

### Git 状态
- 未提交

## 2026-05-05 参考图风格系统架构图生成

### 修改内容
- 以用户提供的黑白流程架构图为版式基准，生成本工程的系统总体架构图。
- 图中保留“底部数据流、中部三视图检测、监督式融合、顶部 RAG/AI Judge/Streamlit 展示”的结构。
- 按当前工程真实实现调整模块名称，包括 Drain 日志模板解析、统计视图 Isolation Forest、时序视图 Bi-LSTM + Attention、语义视图哈希表示与风险锚点、XGBoost / Random Forest 元学习器、FAISS RAG 检索与 AI Judge 报告生成。

### 输出文件
- `reports/final_thesis_package/generate_project_architecture_reference_20260505.py`
- `reports/final_thesis_package/figures_lunwen_publication_20260504/fig6_1_project_architecture_reference_20260505.png`
- `reports/final_thesis_package/figures_lunwen_publication_20260504/fig6_1_project_architecture_reference_20260505.svg`

### 结果说明
- 已生成 PNG 与 SVG 两种格式，适合论文第 6 章系统总体架构图使用。
- 已执行 `python -m py_compile reports/final_thesis_package/generate_project_architecture_reference_20260505.py`，脚本语法检查通过。

### Git 状态
- 未提交

## 2026-05-05 第6章前端插图版正文生成

### 修改内容
- 基于用户提供的第 6 章正文，生成包含前端截图插入位置和图题的优化版 Markdown。
- 将系统架构图、安全态势大盘、事件分析中心、模型解释、RAG 相似案例和 AI Judge 报告界面分别嵌入 6.1、6.3 和 6.4 对应段落。
- 对 6.1 至 6.6 正文进行适度润色，减少重复表述，突出“检测主链路与研判增强层分离”的工程实现逻辑。
- 删除 6.5 中两个具体案例小节，将本章小结重新编号为 6.5，避免章节内容重复和篇幅过长。
- 重新优化图文衔接，为图 6-1 至图 6-6 补充更明确的图前引导和图后说明，避免图片插入显得突兀。
- 为每张图片补充独立加粗图名，并将图后说明调整为“由图可见”的论文式分析表述，增强学术写作风格。
- 将 6.3 拆分为 6.3.1 安全态势大盘、6.3.2 事件分析中心、6.3.3 模型解释与配置管理，使前端展示内容层次更清楚。

### 输出文件
- `reports/final_thesis_package/chapter6_with_frontend_figures_20260505.md`

### 结果说明
- 文档可直接作为论文第 6 章插图版正文使用，图 6-1 至图 6-6 的插入位置与图名已在 Markdown 中明确。
- 图片路径使用当前 `reports/final_thesis_package` 下的相对路径，便于后续复制到论文或转换为 Word。
- 当前结构为 6.1 至 6.5，其中 6.3 下设三个三级小节，6.5 为本章小结。

### Git 状态
- 未提交



## 2026-10-21 LogFusion-Agent MVP

基于 public-upload 新建独立项目，增加规则/LLM 双模式调查、六个只读工具、可追溯证据与报告、原模型/RAG 适配、Streamlit 调查工作台、合成 SSH 场景与自动测试。原始仓库来源记录于 UPSTREAM.md，原检测代码保留。


## 2026-10-21 Agent 检索与综合研判打通

增加 Agent completion 阶段、LLM 结构化综合研判、观察/推断分离、日志与案例引用校验、最多一次修正、共享预算及失败保留证据。工作台新增综合研判页签与逐条引用展开。提供明确标注的无密钥模拟演示及 --llm-judge 混合模式，增加完整链路与失败测试。

## 2026-10-22 阶段 1：事件级评测框架

### 修改内容
- 新增 SSH 标注评测集生成器：固定种子、7 类共 42 条用例，覆盖阳性、无后续成功、异账号、异主机、窗口外、良性重试与多簇误配。
- 标签仅写入 `benchmarks/cases/*.json`，工具只能读到 `*.jsonl`；生成器写盘后用 `failure_clusters` 反解自检，保证标注可达。
- 新增分组评测脚本：规则剧本、模拟研判、真实 LLM 三组；统计结论正确率、证据/关联召回、误关联、跨簇误配、步数、token、完成率、工具报错率与停止原因。
- 新增 13 个评测相关测试（共 62 个），覆盖用例可复现、标签隔离、分类别 verdict、干扰项不误关联、指标聚合。
- 记录首次真实 LLM 评测结果与诊断，指出工具参数范围未写入 schema 导致 100% 运行出现调用错误。

### 输出文件
- `benchmarks/generate_cases.py`
- `benchmarks/run_eval.py`
- `benchmarks/cases/`（42 条用例，含 `manifest.json`）
- `benchmarks/results/eval_rule_20261021T164134Z.json`
- `benchmarks/results/eval_simulated_20261021T164137Z.json`
- `benchmarks/results/eval_llm_20261021T164140Z.json`
- `benchmarks/results/eval_llm_20261021T164242Z.json`
- `tests/test_eval_harness.py`
- `docs/EVAL_REPORT.md`
- `README.md`（新增“事件级评测”一节）

### 结果说明
- 规则组 42/42 结论正确、平均 5.3 步、0 token；模拟研判组同样 42/42，用于验证检索→研判→引用校验链路。
- LLM 组 21 次：结论正确率 0.86、证据召回 0.83、误关联 0、平均 10.1 步 / 71073 tokens、完成率 0.43；8 次撞 12 步上限，2 次因连续工具错误终止。
- 判错 3 例全部源于过早终止（未聚合失败簇），属调查未完成而非判断错误。
- 标注规则与证据层同源，结论正确率存在天花板效应；报告已写明该限制，强调证据召回、成本与完成率才是有效指标。
- 复跑诊断显示 `temperature=0` 仍出现轨迹差异，需多次重复取均值。

### Git 状态
- 未提交

## 2026-10-22 阶段 1 补充：迁移上游训练产物，跑通 A/D 两组

### 修改内容
- 从本地前身工程 `log_analysis_system_complete` 迁移真实训练产物：融合 XGBoost、Isolation Forest、Bi-LSTM 检查点与 67 条案例向量索引（不进入 Git）。
- 检测器适配层新增 `windows` 字段，暴露每个风险分对应的序列窗口跨度；修正“只取末行事件”导致标注事件永远不可见的问题。
- 新增 `benchmarks/oneshot.py`：A 组为上游一次性基线，展开最高风险窗口作为证据，再用共享结论层推导 verdict。
- `run_eval.py` 增加 `upstream` 与 `agent+upstream` 两组，并新增“证据精度”指标，用于暴露窗口级证据召回高、精度低的问题。
- D 组预算与 schema 修复后的 C 组对齐为 16 步。
- C 组在修复前后各有一版结果：C0（旧 schema，12 步）与 C1（新 schema，16 步），报告中已标明两变量混杂。

### 输出文件
- `benchmarks/oneshot.py`
- `src/agent/adapters.py`（窗口跨度）
- `benchmarks/run_eval.py`（两个新分组 + 证据精度）
- `benchmarks/results/eval_upstream_20261021T233851Z.json`
- `benchmarks/results/eval_agent+upstream_20261021T234451Z.json`
- `benchmarks/results/eval_rule_simulated_20261021T235121Z.json`
- `UPSTREAM.md`（迁移产物来源与限制）
- `docs/EVAL_REPORT.md`（重写：五组结果、停止原因、RAG 索引限制）
- `README.md`（迁移清单与 A/D 命令）

### 结果说明
- A 组 42 条：结论正确率 1.00、证据召回 1.00、证据精度 0.14、2 步、0 token、完成率 0.95（2 条 49 行日志不足 50 条窗口）。
- D 组 21 条：结论正确率 1.00、召回 1.00、精度 0.18、11.8 步、88768 tokens、完成率 0.52；9/21 撞 token 预算，因为检测器一次返回 30 条分数加窗口跨度。
- 迁移的向量索引在哈希嵌入下最高相似度约 0.14，低于 0.65/0.7 阈值，`retrieve_cases` 实际返回空；D 组差异只来自检测器。
- 证据精度显示 A 组虽然召回满分，但每次要看约 50 条窗口日志才能覆盖 7–8 条标注事件。

### Git 状态
- 未提交

## 2026-10-22 新增工程问题记录

### 修改内容
- 新建 `docs/ENGINEERING_ISSUES.md`，按“调查与工具层 / 评测框架 / 上游集成 / 环境与协作 / 未解决清单 / 经验”归类记录实施过程中真实遇到的 16 个工程问题。
- 每条包含现象、影响、根因、定位方式、处置与状态，并附可核对的结果文件或数字（如工具报错率 1.00→0.24、窗口证据精度 0.14、索引相似度 0.1431、软预算 104331 tokens）。
- 明确区分“已修复”“已规避”“未解决”“方法论限制”，未把已知缺陷写成已解决。
- README 的评测章节增加指向该文件的入口。

### 输出文件
- `docs/ENGINEERING_ISSUES.md`
- `README.md`（新增一行索引）

### 结果说明
- 未解决项集中在：语义检索不可用（哈希嵌入）、C0→C1 变量混杂、检测器上下文膨胀、用例长度下限、重复次数不足、阶段 4 工程缺口。
- 环境类问题（控制台编码、PowerShell heredoc、stderr 被包装成错误、EIO 写入失败、并行会话冲突）单独成节，便于后续会话复用排查经验。

### Git 状态
- 未提交

## 2026-10-22 有界工具观察、双锚点修复、剧本失效集

### 修改内容
- `detect_anomalies` 改为只返回 top-N 窗口（默认 5，schema 范围 1..10），每个窗口带跨度、风险分、主要贡献视图与三视图分数，不再返回逐条原始分数；单次观察从约 10 KB 降到 876 字符。
- 新增 `_fit_observation`：所有工具结果统一 6000 字符上限，超限时裁剪首个大列表并写 `observation_truncated`，供后续 Web 场景工具复用。
- 修复窗口只记录结束锚点的问题：开始与结束锚点都写入证据，模型查询 `start_event_id` 上下文不再报未知事件；D 组工具报错率 0.67 → 0.10。
- 新增 `benchmarks/generate_hard_cases.py` 与 `benchmarks/cases_hard/`：4 类剧本结构性失效用例（分布式喷洒、低速、单 IP 多账号、跨主机成功），生成器断言无失败簇。
- `run_eval.py` 增加 `--cases-dir` 与结果中的 `git_sha`，C 组预算对齐到 16 步。
- 新增 7 个观察上限测试（共 74 个），覆盖窗口裁剪、参数越界、未知事件、通用上限。

### 输出文件
- `src/agent/tools.py`、`src/agent/adapters.py`、`src/agent/planner.py`
- `benchmarks/generate_hard_cases.py`、`benchmarks/cases_hard/`
- `benchmarks/run_eval.py`（`--cases-dir`、`git_sha`）
- `tests/test_observation_limits.py`
- `benchmarks/results/eval_llm_20261021T235856Z.json`（C1）
- `benchmarks/results/eval_agent+upstream_20261022T000601Z.json`（D）
- `benchmarks/results/eval_rule_20261022T000633Z.json`（B·失效集）
- `benchmarks/results/eval_llm_20261022T001220Z.json`（C1·失效集）
- `benchmarks/results/eval_agent+upstream_20261022T001220Z.json`（D·失效集）
- `docs/EVAL_REPORT.md`、`docs/ENGINEERING_ISSUES.md`

### 结果说明
- 标准集 D 组：完成率 0.52 → 0.81，平均 token 88768 → 77216，工具报错率 0.67 → 0.10；结论正确率仍与 C1 打平。
- 剧本失效集：B 召回 0.00，C1 与 D 召回 1.00；但 D 精度更低（0.35 vs 0.44）、更贵（98505 vs 89849 tokens），完成率同为 0.33。
- 结论：Agent 的价值体现在“规则看不见时仍能取证”，检测器在当前哈希嵌入与窗口粒度下没有带来增量；失效集瓶颈转为预算。
- 代码已提交：500ba60、307a658、27e147d、0e1c85a；结果 JSON 记录运行时 SHA。

### Git 状态
- 结果文件与文档待提交

## 2026-10-22 结论层补规则 + Agent 收尾降级

### 修改内容
- 结论层新增三类证据规则：同账号 10 分钟内被 ≥8 个来源 IP 尝试（分布式喷洒）、同来源 10 分钟内对 ≥8 个账号尝试（撞库）、同实体 30 分钟内 ≥10 次且任意 5 分钟 <5 次（低速爆破）；并为其成功登录建立关联。跨主机成功登录按设计仍不关联。
- 失效集生成器同步更新期望 verdict（三类为 correlated_success，跨主机为 no_correlated_success），标准集 42 条无新增误报。
- 工具层：`search_logs` 默认紧凑投影（仅定位字段）并做已见去重，重复命中只返回新事件；`aggregate_events` 增加 `group_by=user/ip/host` 跨来源汇总；新增 `reset()` 清理每轮状态。
- Agent 收尾：预留 ≥2 步与 ≥1/3 token 给案例检索和综合研判；工具预算用尽改为 `evidence_budget` 收束；重复调用回灌提示后继续；连续工具错误降级收束；研判被拒只标注未发布，不再把整次调查判为失败。
- 新增 11 个测试（共 85 个），覆盖三类规则、跨主机不关联、紧凑投影、去重、跨源聚合、收尾降级。

### 输出文件
- `src/agent/engine.py`（规则 + 收尾 + 降级）
- `src/agent/tools.py`（紧凑投影、去重、group_by、reset）
- `benchmarks/generate_hard_cases.py`（期望 verdict）
- `tests/test_pattern_rules.py`
- `docs/ENGINEERING_ISSUES.md`（新增 1.6、2.7）
- `docs/AGENT_DESIGN.md`、`README.md`（Agent 循环与收尾）
- `docs/EVAL_REPORT.md`（5.5 流程完成性冒烟）

### 结果说明
- 失效集 3 条冒烟：完成率 1.00（1 次 evidence_budget、1 次 planner_finished、1 次 judgment_rejected 但仍出报告），平均 11 步、78655 tokens。
- 结论层补规则后，失效集“查全了也判不出”的问题消除；B 组仍因取证路径受限保持 0 召回，盲区成立。
- 未做全量重复实验，数字只作流程可用性冒烟，不作为效果结论。

### Git 状态
- 未提交

## 2026-10-22 收尾模式与完成率验收

### 修改内容
- Agent 预算改为三段：工具阶段（2/3 token、max_steps-2 步）、收尾模式（token 75% 或只差 2 步时触发）、收尾阶段（保留 ≥2 步与 ≥1/3 token）。
- 收尾模式下追加“停止探索”系统指令，工具只剩 build_timeline / retrieve_cases / finish_investigation；越权调用返回提示，连续 2 次才收束。
- 状态拆分 completed / completed_partial；规划器异常、连续工具错误、研判被拒都降级为 completed_partial，报告仍产出。
- 研判校验失败时在重试提示里给出具体未知 ID，便于模型自我修复。
- 评测新增 completion_rate（含部分完成）与 partial_rate，并在汇总表分列。
- 修复结果文件名冲突：同秒启动的两次评测会互相覆盖，文件名加入数据集名。

### 输出文件
- `src/agent/engine.py`、`src/agent/planner.py`、`src/agent/judgment.py`
- `benchmarks/run_eval.py`
- `benchmarks/results/eval_cases_llm_20261022T005608Z.json`（标准集 42 次）
- `README.md`、`docs/ENGINEERING_ISSUES.md`、`docs/EVAL_REPORT.md`

### 结果说明
- 标准集 42 次：完成率 0.95（完全完成 0.52、部分完成 0.43），停止原因以 evidence_budget 13、planner_finished 22 为主；token_budget 仅 1 次、tool_error_limit 0 次、repeated_tool_call 0 次。
- 失效集 12 次：完成率 0.92（完全完成 0.08、部分完成 0.83），evidence_budget 4、judgment_rejected 6、planner_finished 1、time_budget 1。
- 失效集“完全完成”偏低，说明预算与取证方式仍偏紧；这是下一步加“假设/理由”和“完整性闸门”的理由。

### Git 状态
- 未提交

## 2026-10-22 计划、每步理由与假设状态

### 修改内容
- 新增计划阶段：`planner.plan()` 在调查前产出 2–4 条假设，写入 `InvestigationResult.plan`，编号 H1..H4，初始 open；规划失败不阻塞调查。
- 所有工具 schema 增加可选 `rationale`；引擎从参数中取出并写入轨迹，不传给工具，避免污染调用参数。
- 新增只读工具 `update_hypothesis(hypothesis_id, status, note)`：confirmed/refuted 由模型声明，引擎更新计划并记录 `updated_at_step`；未知 ID 只报错不改状态。
- 报告新增“调查计划与假设”一节，工具执行记录带理由；Streamlit 工作台展示计划、状态与每步理由，并区分 completed 与 completed_partial。
- 规则剧本同步：固定三条假设，并在聚合、成功登录、上下文三个阶段更新假设，使离线演示也具备“假设→动作→更新”结构。

### 输出文件
- `src/agent/engine.py`、`src/agent/planner.py`、`src/agent/tools.py`
- `frontend/agent_app.py`
- `tests/test_plan_trace.py`（7 个新测试，共 91 个）
- `README.md`、`docs/AGENT_DESIGN.md`

### 结果说明
- 单条真实模型冒烟（ssh-001）：模型自发提出 4 条假设（含账户枚举/横向移动），把 H1 标为 confirmed，并对 aggregate/get_event_context/detect/update_hypothesis 各写了理由；运行以 completed_partial 收尾，78k–82k tokens。
- 规则模式 demo 报告可看到 H1/H2/H3 全部 confirmed 及三条更新理由。
- 未做批量统计；轨迹质量目前靠人工查看，后续可加“理由覆盖率/假设更新率”指标。

### Git 状态
- 未提交

## 2026-10-22 完整性闸门、演示套件与轨迹指标

### 修改内容
- 完整性闸门：申请 `finish_investigation` 时检查三类覆盖——每个失败簇是否查过后继成功登录、簇后 15 分钟内同账号同主机的成功登录是否核对过上下文、计划假设是否全为 open；另拒绝“未看任何证据就结束”。最多退回 2 次，缺口写入 `limitations`，闸门条目用 `control` 标记、不计工具错误。
- 新增 `--demo-suite`：同一 Agent 依次跑经典暴力破解、分布式喷洒、良性重试，打印假设、每步理由、停止原因与闸门次数，并给出轨迹对比。
- 评测新增 `gate_triggers`、`rationale_rate`、`hypothesis_rate` 三个指标，汇总行同时展示完全完成与部分完成。
- 修复收尾阈值 bug：原先 75% token 阈值高于工具硬上限（67%），收尾模式永远不触发；改为工具上限的 90%。收尾模式允许 `update_hypothesis`，并提示先给假设结论再结束。
- `rationale` 改为 schema 必填；步数预算从 16 提到 20，避免 15 步轨迹必然进入收尾。

### 输出文件
- `src/agent/engine.py`、`src/agent/planner.py`、`src/agent/tools.py`
- `src/agent/__main__.py`（`--demo-suite`）
- `benchmarks/run_eval.py`（三个新指标）
- `tests/test_completeness_gate.py`（4 个新测试，共 95 个）
- `README.md`、`docs/AGENT_DESIGN.md`、`docs/EVAL_REPORT.md`

### 结果说明
- 16 步配置的验收：标准 21 条与失效 12 条完成率均为 1.00，`token_budget`/`tool_error_limit`/`repeated_tool_call` 归零；但理由覆盖 0.18、假设结论率 0.06–0.15、闸门 0 次，原因是轨迹在 12 步进入收尾、模型几乎不主动结束。
- 随后修正阈值并提高预算，6 条小样本验证：见 `docs/EVAL_REPORT.md` 5.7；不作为统计结论。

### Git 状态
- 未提交

### 补充：收尾阈值与闸门验证
- 发现收尾阈值高于工具上限（75% > 67%），收尾模式永不触发；改为工具上限的 90%。
- 20 步 / 100k 的 6 条小样本：完成率 1.00（全部部分完成），理由覆盖 0.25–0.37、假设结论率 0.08–0.33、闸门 0 次；150k 预算会让模型探索更久（21 步、135k、完成率 0.67），已回退到 16 步。
- 结论：闸门只在“申请结束”时检查，而模型倾向探索到预算耗尽，从不主动结束；下一步需把收尾改为终端阶段（一次整合后强制收口）。

## 2026-10-22 收尾终端化与终局闸门

### 修改内容
- 收尾改为终端阶段：`WRAP_UP_TURNS = 2`，第一轮用于 `update_hypothesis` 收束假设，第二轮是强制结束轮（只暴露 `finish_investigation` 并锁定 `tool_choice`）；供应商忽略强制选择时记录 `ignored_tool_call` 并按结束处理。
- 收尾起点改为按观测单轮成本动态预留（`1.5 × 已用/已做动作数`，且不超过工具预算一半），替换原“工具上限 90%”的固定比例——固定比例可能被单次调用一步跨过，导致收尾被置位又跳过。
- 收尾阶段可动用一半完成预留 token（`tool_token_limit + reserve//2`，不超过 `max_tokens`），保证关门轮与研判都不会被提前砍断。
- 闸门语义调整：非收尾阶段仍可退回 2 次；收尾阶段的结束请求若有缺口，拒绝一次即按 `gate_unresolved` 收口，缺口写入 `limitations`（原先收尾只检查假设项，等于放行探索缺口）。
- 循环后新增终局审计：未经 `planner_finished` 结束且闸门从未触发时，再评估一次覆盖缺口，记为 `terminal: true` 的闸门条目，`stop_reason=wrap_up_terminal`，避免“没申请结束 = 覆盖完整”的假象。
- 评测新增 `gate_terminal_refusals`（终局被拒绝次数），汇总行与 `gate_triggers` 并列输出。

### 输出文件
- `src/agent/engine.py`、`src/agent/planner.py`
- `benchmarks/run_eval.py`
- `tests/test_completeness_gate.py`（4 个新测试，共 99 个）
- `docs/AGENT_DESIGN.md`

### 结果说明
- `pytest`：99 passed。
- 规则 `--demo-suite`：三条轨迹仍为 `completed/planner_finished`，闸门 0 次（覆盖完整，无需拦截），轨迹与收尾阈值改动前一致。
- 真实模型 3 条（ssh-001/002/003，16 步 / 100k）：完成率 1.00（完全完成 0.33），`gate_unresolved` 2 次、`planner_finished` 1 次，闸门 0.7 次/次（其中终局拒绝 2 次），理由覆盖 0.42，假设结论率 0.25，证据召回 1.00、精度 0.26，平均 17.3 步 / 92.9k tokens。该批次跑在 `gate_terminal_refusals` 字段加入之前，终局拒绝次数由 `stop_reason=gate_unresolved` 计得。
- 单条 ssh-001 全轨迹复核：13 步进入收尾 → 一次 `update_hypothesis` → 14 步强制结束轮 → 闸门拒绝（缺口为“失败簇 … 尚未查询后续成功登录”）→ `gate_unresolved`，研判照常发布并在 `limitations` 披露缺口与拒绝原因。
- 闸门不再是“永不触发的代码”：三条用例中 2 条被真实拒绝，1 条自主结束且无缺口（按设计返回 0）。

### Git 状态
- 已提交

## 2026-10-22 重建 RAG 案例索引（TF-IDF）

### 修改内容
- 新增 `scripts/rebuild_rag_index.py` 与 `src/agent/rag_index.py`：离线重建 67 条案例索引（TF-IDF，2114 维），同时保留 `--backend minilm` 入口，供联网环境替换为句向量。
- Agent 检索优先使用 `local_tfidf_cases`，返回 Top-K、raw_score 与 match_level（strong ≥0.35 / medium ≥0.2 / weak）；不再依赖哈希索引与 0.65/0.7 阈值。
- `retrieve_cases` 对向量后端统一回传候选与匹配强度；哈希后端仍保留“原始日志构造查询”的兼容分支。
- 新增 3 个索引测试（排序正确、确定性、弱匹配标注），共 102 个测试。

### 输出文件
- `scripts/rebuild_rag_index.py`
- `src/agent/rag_index.py`
- `src/agent/adapters.py`、`src/agent/tools.py`
- `tests/test_rag_index.py`
- `docs/EVAL_REPORT.md`（3.3 重写）、`docs/ENGINEERING_ISSUES.md`（3.1 结案）、`README.md`、`reports/resume_project_logfusion_agent.md`

### 结果说明
- 样例查询 Top-1 全部命中：failed password → SSH brute force（0.323）、accepted root → root login success（0.400）、sudo → privilege escalation（0.164）、AH01630 → restricted resource probing（0.349）。
- 索引离线、确定性，不依赖网络；句向量版本因 HF 不可达暂未生成，接口已预留。

### Git 状态
- 未提交

## 2026-10-22 本地 MiniLM ONNX 检索路线

### 修改内容
- 在 VS Code Continue 扩展目录找到本地 `all-MiniLM-L6-v2` ONNX（384 维），安装兼容的 onnxruntime 1.19.2（1.31 在本机 DLL 崩溃），实现 `MiniLMOnnxEncoder`（tokenizers + mean pooling + L2 归一化）。
- `scripts/rebuild_rag_index.py` 支持 `--backend minilm --model-dir`，生成 384 维索引与模型目录 sidecar；`--backend tfidf` 仍为默认。
- Agent 检索后端优先级：TF-IDF → MiniLM → 上游哈希索引；日志/文档标明每条路线的分数口径。
- 新增 MiniLM 检索测试（索引存在时执行）。

### 结果说明
- 同一批查询 Top-1：TF-IDF 5/5 正确，量化 MiniLM 2–3/5（`failed password` 会排到“成功登录”案例，`SSH brute force` 会排到 root 登录）；因此默认仍用 TF-IDF，MiniLM 作为可切换语义后端。
- 该结果与论文一致：embedding 语义视图单独更强，但融合模型在 hash 特征上更强，canonical 选 hash。
- onnxruntime 1.31 在 Python 3.12 下导入即 access violation，降到 1.19.2 后正常。

### 输出文件
- `src/agent/rag_index.py`（MiniLM 编码器/索引/检索）
- `scripts/rebuild_rag_index.py`（`--backend minilm`）
- `src/agent/adapters.py`（后端优先级）
- `tests/test_rag_index.py`
- `README.md`、`docs/EVAL_REPORT.md`、`reports/resume_project_logfusion_agent.md`

### Git 状态
- 未提交

## 2026-10-22 混合检索（TF-IDF + MiniLM，RRF）

### 修改内容
- 新增 `HybridCaseRetriever` 与 `reciprocal_rank_fusion`：两路各取 Top-10，按排名融合，不依赖分数量纲；返回体同时给出 `tfidf_score`、`minilm_score` 与综合 `match_level`。
- 默认后端改为 `local_hybrid_cases`；`AGENT_RAG_BACKEND=tfidf|minilm|hash` 可强制切换。
- 新增 2 个测试（RRF 融合、混合检索），共 105 个测试。

### 结果说明
- 13 条查询（8 条日志式 + 5 条改写）Top-1：TF-IDF 10/13、MiniLM 9/13、Hybrid 11/13。
- 日志式查询三者都接近满分（TF-IDF 8/8、Hybrid 8/8、MiniLM 6/8）；改写查询 MiniLM 与 Hybrid 3/5，优于 TF-IDF 2/5。
- 结论：混合检索在不牺牲精确匹配的前提下补上了改写查询的覆盖。

### 输出文件
- `src/agent/rag_index.py`、`src/agent/adapters.py`
- `tests/test_rag_index.py`
- `README.md`、`docs/EVAL_REPORT.md`、`reports/resume_project_logfusion_agent.md`

### Git 状态
- 未提交

## 2026-10-22 检索鲁棒性与可复现评估

### 修改内容
- 查询归一化 `normalize_query`：去除时间戳、IP、端口、sshd PID、纯数字，降低日志噪声对词面匹配的影响（TF-IDF 分数略升、Top-1 不变）。
- 鲁棒性：TF-IDF/MiniLM 检索加 LRU 式查询缓存；索引或模型损坏时逐级降级（hybrid → tfidf → minilm → 上游哈希），`retrieve_cases` 捕获检索异常并返回“检索不可用”，不再中断调查。
- 新增 `benchmarks/rag_queries.json`（13 条标注查询）与 `scripts/evaluate_case_retrieval.py`，输出 Top-1/Top-3 与日志式/改写分项，结果写入 `benchmarks/results/rag_retrieval_eval.json`。
- 新增 3 个测试（归一化、检索异常隔离、混合检索排序），共 107 个测试。

### 结果说明
- 13 条查询 Top-1：TF-IDF 0.77、MiniLM 0.69、Hybrid **0.85**；Top-3 均为 0.92。
- 分项：日志式 Top-1，TF-IDF 与 Hybrid 均 1.00、MiniLM 0.75；改写 Top-1，MiniLM 与 Hybrid 0.60、TF-IDF 0.40。
- 该评估为 agent 侧小样本 sanity check，不是论文的样本级命中率协议；论文数字仍以句向量环境为准。

### 输出文件
- `src/agent/rag_index.py`、`src/agent/adapters.py`、`src/agent/tools.py`
- `benchmarks/rag_queries.json`、`scripts/evaluate_case_retrieval.py`、`benchmarks/results/rag_retrieval_eval.json`
- `tests/test_rag_index.py`
- `README.md`、`docs/EVAL_REPORT.md`、`reports/resume_project_logfusion_agent.md`

### Git 状态
- 未提交

## 2026-10-22 标注模板级检索评估（104 条）

### 修改内容
- 从前身工程的 AIT-LDS v2 解析数据与标签导出 104 条“异常模板 → 期望 attack_type”样本（harrison 27 / santos 51 / fox 26），写入 `benchmarks/labeled_templates.json`。
- 新增 `scripts/evaluate_rag_on_labeled.py`：按上游脚本口径计算 type@1/3/5 与 group@1/3/5，覆盖哈希、TF-IDF、MiniLM、混合四种后端。
- 权重扫描发现等权 RRF 会被较弱的 TF-IDF 拖累（type@1 0.538），1:6 加权后与 MiniLM 持平；默认后端改为 MiniLM，混合保留 `AGENT_RAG_BACKEND=hybrid`。
- 新增加权 RRF 测试，共 108 个测试。

### 结果说明
- 104 条标注模板 type@1：哈希 0.798、TF-IDF 0.567、MiniLM **0.894**、混合 0.894；type@3：0.923 / 0.769 / 0.971 / 0.971。
- group@1 全为 1.0，因为三个子集的异常模板几乎都属于 security_attack，该指标无区分度，以 attack_type 为准。
- 13 条手工查询作为辅助：日志式 TF-IDF/混合 1.00、MiniLM 0.75；改写 MiniLM/混合 0.60、TF-IDF 0.40。

### 输出文件
- `benchmarks/labeled_templates.json`
- `scripts/evaluate_rag_on_labeled.py`
- `benchmarks/results/rag_labeled_eval.json`
- `src/agent/rag_index.py`（加权 RRF）、`src/agent/adapters.py`（默认 MiniLM）
- `tests/test_rag_index.py`
- `README.md`、`docs/EVAL_REPORT.md`、`reports/resume_project_logfusion_agent.md`

### Git 状态
- 未提交

## 2026-10-22 全流程自检与修复

### 检查范围
- `pytest`（108 个）、`--demo`（rule / simulated）、`--demo-suite`、`--with-detector` 单例、`--vector-rag` 单例、`--mode llm` 全链路（检测器 + RAG）、`run_eval --groups rule/upstream`、Streamlit 模块编译与导入、异常路径（缺失输入）。

### 修复的问题
- RAG 案例缺 `raw_score` / `match_level`：投影白名单只认 `upstream_vector_rag` 与 `local_tfidf_cases`，漏了 `local_minilm_cases` / `local_hybrid_cases`，已改为“非词法后端一律投影”。
- 检测器不可用时没有披露：日志不足 50 条时 `detect_anomalies` 报错后仍继续，但报告未说明，已补限制“检测器不可用，结论仅基于规则信号与日志检索”。
- trace 步号跳号/重复：收尾与完成阶段用 `len(trace)+1` 计算，遇到 plan/gate/wrap_up 记录会错位；改为 `max(step)+1`。
- 评测步数口径失真：`tool_steps` 把 plan、闸门、收尾通知都算成工具步，导致 rule 组从 5.3 步涨到 9.3；改为只统计真实工具动作。

### 结果
- 标准集 rule 组：结论 1.00、召回 1.00、理由覆盖 1.00、假设结论率 1.00、平均 9.0 步。
- 全链路（检测器 + MiniLM RAG）：completed_partial / gate_unresolved、86k tokens、证据 20 条、研判发布；案例带分数（0.597 / 0.498 / 0.494）。
- demo-suite 三条轨迹均 completed 并出报告。

### 仍存在的问题
- 模型对 `rationale` 必填遵守度约 40%（schema 必填但服务端未强制），评测中已按覆盖率记录。
- 闸门只在“申请结束”时检查；收尾阶段被拒即结束，而模型常在收尾前没查失败簇的后继登录，导致 gate_unresolved。
- `gate_unresolved` 的报告措辞仍是“未正常完成”，可改为“收尾阶段被完整性闸门拦下”。
- `outputs/investigations` 无清理机制。

### Git 状态
- 未提交

## 2026-10-22 前置完整性提示与验收数据

### 修改内容
- 发现失败簇后（`aggregate_events` 返回 groups）注入一次性 `required_action` 提示，要求先查同实体后继登录；仅在已用 token < 工具预算 60% 时注入，避免提示本身把预算烧穿。
- 收尾被闸门拦下时，限制文案改为“收尾阶段被完整性闸门拦下：未覆盖项见上，报告作为部分完成发布”，不再笼统写“未正常完成”。
- 评测 `tool_steps` 排除 hint 控制条目。
- LLM 评测预算调整为 16 步 / 130k tokens（原 100k）。

### 结果说明
- 失效集 12 条：完成率 0.92（完全 0.75 / 部分 0.17），撞 token 预算从 4 次降到 1 次，闸门 0.1 次/次；平均 13.8 步、109810 tokens。
- 标准集 21 条（16 步 / 100k）：完成率 1.00（0.05 / 0.95），token_budget 1 次。
- 理由覆盖 0.32、假设结论率 0.23：模型对必填字段遵守度有限，按实际值记录。
- 简历新增“工程能力与数据”一节：负责范围、痛点→处理→数据表、三条面试主线。

### 输出文件
- `src/agent/engine.py`、`benchmarks/run_eval.py`
- `docs/EVAL_REPORT.md`、`reports/resume_project_logfusion_agent.md`
- `benchmarks/results/eval_cases_hard_llm_20261022T035824Z.json`

### Git 状态
- 未提交

## 2026-10-22 上下文成本优化：折叠 / 台账 / 空结果熔断

### 修改内容
- `planner.py`：抽出 `build_messages()`（`fold` 与 `compact` 两种历史策略，`fold=False` 保留旧行为）、`project_observation()`、`fold_observation()`、`build_ledger()`、`_brief()`。折叠为**保形**投影：`events/groups/cases` 仍是列表，只留定位字段，行数截到 6，丢弃 `raw/source/line`；小于 420 字符的观察不折叠。
- `planner.py`：新增 `LLMPlanner._account()`，单独累计 `prompt_cache_hit_tokens` → `cached_tokens`；`AGENT_HISTORY_MODE=full|fold|compact`（默认 fold）。
- `engine.py`：新增 `is_empty_observation()` 与空结果熔断——连续 2 次空集注入 `EmptyResultHint`，第 3 次提前进入收尾（wrap_up 提示改为按原因区分文案）。
- `engine.py`：`InvestigationResult` 新增 `tokens_cached`。
- `benchmarks/run_eval.py`：新增 `tokens_cached`、`empty_calls` 逐例字段与 `mean_tokens_cached`、`mean_empty_calls` 汇总，总体行输出缓存命中与空结果调用。
- 新增 `benchmarks/measure_context.py`：离线回放 `outputs/investigations/*/investigation.json`，对比 full / fold / compact 三种策略的 payload 成本，不需要 API key。
- 新增 `tests/test_context_budget.py`（7 个测试）：折叠降体积且保留全部证据 ID、小观察不折叠、台账严格更省、观察投影截断、空结果判定、熔断触发提示并提前收口、缓存命中与预算分离记账。
- 新增 `reports/resume_token_efficiency.md`：面向简历的归因、改动、数据、边界与面试问答。

### 依据
- 调用级重算 INV-a629dd03638c（16 次调用 / 88,615 token）：固定开销 29%、历史重发 70%、输出 1.4%；自建估算模型给出 84,771，误差 4%。
- 回放 44 条轨迹 / 378 次调用：折叠 961,692 → 830,534（−13.6%），≥10 步 19 条 603,489 → 506,656（−16.0%），最长 16 步 52,628 → 40,981（−22.1%）；台账 691,677（−28.1%）/ ≥10 步 −33.7% / 16 步 26,597（−49.5%）。空结果 20/378（5.3%），10 条轨迹受影响，单条最多 7 次。

### 结果说明
- `pytest`：115 passed（原 108 + 7）。
- 规则模式冒烟（12 条失效集）：完成率 1.00、证据召回 1.00、平均 8.7 步、空结果 0.3 次/次，管线正常。
- **未做真实模型复测**：DeepSeek 账户余额为 0，`/user/balance` 返回 `is_available=false`，任何 LLM 调用 402。台账模式的行为等价性待余额恢复后用 `--limit 3 --repeats 3` 对照，通过后再考虑改默认。
- 折叠不改变 trace，因此闸门与引用校验的行为不变（`_coverage_gaps` / `validate_judgment` 读 trace 与工具层状态）。

## 2026-10-22 追加：上下文管理提升为独立架构层

### 修改内容
- 新增 `src/agent/context.py`：模块 docstring 定义三层记忆（指令层 / 工作记忆 / 情景台账）与三条策略；`ContextPolicy` 为 frozen dataclass（`mode` / `recent_items` / `fold_min_chars` / `event_rows`），提供 `from_env()`、`build()`、`layout()`；`project_observation` / `fold_observation` / `build_ledger` / `_brief` 迁入该模块。
- `planner.py`：改为 `self.policy = ContextPolicy.from_env()`、`messages = self.policy.build(...)`，并保留 `build_messages()` 作为向后兼容包装（测试与离线回放仍从 planner 导入）。
- `docs/AGENT_DESIGN.md`：该节重写为架构视角——三层记忆图、与控制回路的三个耦合点（收尾触发 / 预算口径 / 不变量）。
- `reports/resume_project_logfusion_agent.md`：能力清单加"上下文管理"行；主版加"上下文层（Context Engineering）"要点；压缩版把分层写进工程治理；三条主线扩为四条。
- `reports/resume_token_efficiency.md`：重写为架构文档（架构图、能力映射表、问答改为架构向）。

### 结果说明
- `pytest`：118 passed（原 115 + 3 个策略层测试：非法 mode 回退、`layout()` 三层计数、full 模式等价旧行为）。
- 离线回放结果与重构前完全一致（fold −13.6% / ≥10 步 −16.0%，compact ≥10 步 −33.7%），说明抽取未改变行为。
- 仍未做真实模型 A/B（余额 0）。

## 2026-10-22 日志方言层：LogProfile

### 修改内容
- 新增 `src/agent/profiles.py`：`LogProfile`（`rules` 有序谓词 / `failure_type` / `success_type` / `escalation_types` / `completion_query` / `label` / `user_patterns`）+ `all_of` / `any_of` / `regex` 组合子 + `get_profile()` 回退。实现 `ssh_auth`（默认）与 `auth_generic`。
- `events.py`：分类与账号抽取改为 profile 驱动；`EventStore` 记住 `profile`，`from_bytes` / `from_path` 支持传入。
- `tools.py` / `engine.py`：`failure_clusters` 增加 `failure_type` 参数；覆盖检查、结论生成、完成阶段查询、限制文案全部按 `store.profile` 渲染。
- `planner.py`：`SYSTEM_PROMPT` 改为 `SYSTEM_PROMPT_TEMPLATE` + `system_prompt(profile)`；`RulePlanner` / `LLMPlanner` / `from_env` 接受 profile。
- `engine.py`：构造时把 planner 的 profile 同步为 `store.profile`，避免提示词与日志方言错配。
- `__main__.py`：新增 `--profile`（choices 来自 PROFILES，未知值回退默认）。
- 新增 `tests/test_profiles.py`（7 个）：SSH 方言行为不变、通用方言分类、跨方言不误分类、非 SSH 端到端产出结论、提示词渲染、未知 profile 回退、规则剧本使用 profile 的成功类型。

### 结果说明
- `pytest`：125 passed（118 + 7）。
- `ssh_auth` 行为与改造前一致（原 118 个测试全绿，未改断言）。
- 非 SSH 方言实测：7 条 RADIUS 风格合成日志 → `completed / planner_finished`，2 条结论（`suspected_bruteforce`、`success_after_failures`），7 条证据全部可引用，报告限制文案为“第一版仅对通用认证日志…”。
- 边界：profile 换方言不换安全语义，结论规则与案例库仍属认证域；Web / 进程行为需新结论规则，未实现。

## 2026-10-22 计划阶段去 SSH 硬编码：profile 渲染 + 数据概况注入

### 问题
`PLAN_PROMPT` 首句写死 `You plan a read-only SSH log investigation`，且 `plan()` 不接收日志概况。结果是：无论上传什么日志，模型都按「SSH 爆破 → 成功登录 → 提权」这条链提假设。多源场景下假设与数据无关，属于真实缺陷而非措辞问题。

### 修改
- `planner.py`：`PLAN_PROMPT` → `PLAN_PROMPT_TEMPLATE` + `plan_prompt(profile, digest)`；首句改为 `over {label}`，第二行注入 `The uploaded logs contain: {digest}`；提示词明确要求"按实际存在的事件类型提假设，多方言并存时覆盖跨源关联，不要假定单一认证叙事"。
- `planner.py`：`LLMPlanner.plan(goal, digest="")` 与 `RulePlanner.plan(goal, digest="")`；规则剧本改用 `profile.failure_type` / `profile.success_type`，不再写死中文"认证失败"。
- `engine.py`：新增 `_data_digest()`，统计事件类型分布、主机数、来源 IP 数、可解析时间戳数，在 `run()` 调 `plan()` 时传入。
- 测试：两处 fake planner 的 `plan` 签名同步为 `(self, goal, digest="")`。

### 结果说明
- `pytest`：125 passed。
- 2 MB 多源切片（11,022 事件 / 4 类源）实测 digest：`other×10815、auth_success×207；主机 165 个、来源 IP 8 个；5307 条带时间戳`，提示词首行渲染为 `over 通用认证日志`。
- **未验证项**：多源假设的实际生成质量需要 LLM 模式，当前账户余额为 0，无法复测。
- **暴露的边界**：11,022 条中 10,815 条仍归为 `other` —— 说明多源支持在**输入端**成立，在**语义端**只有认证类方言，VPN / DNS / audit 的分类规则尚未实现。

## 2026-10-22 补：plan 输出截断导致计划阶段一直静默失败

### 问题
`plan()` 的 `max_tokens=400` 对 2–4 条中文假设的 JSON 不够，返回的 tool-call payload 被截断在 ~528 字符，
`json.loads` 抛 `JSONDecodeError`，被 `run()` 的 `except Exception` 吞掉 → **plan 恒为空**，且无任何日志。
此前所有 LLM 轨迹的「有计划」其实只在短假设时成立，长假设一律丢失。

### 修改
- `max_tokens=400` → `900`。
- `json.loads` 包 try/except：解析失败返回 `[]` 并依赖"规划可选"语义继续，不抛异常中断。

### 验证（真实模型，2 MB 多源切片）
- 修复前：`plan=[]`，tokens 20,655（模型直接开跑）
- 修复后：生成 4 条数据驱动假设，tokens 25,270（缓存命中 14,208），`completed_partial / gate_unresolved`
- 假设内容完全基于 digest，无 SSH 字样：
  - H1 跨源关联：10,815 条 other 中按 8 个来源 IP / 165 个主机聚集的短时突发，其后是否出现 auth_success
  - H2 auth_success 集中度：207 条在 8 IP / 165 主机上的分布是否偏离运维基线
  - H3 **时间戳可解析性偏差**：11,022 条中仅 5,307 条有时间戳，若缺失在类型/IP 上系统性偏向，则时间分析需降级
  - H4 other 中的失败/拒绝语义是否先于同源对同主机的 auth_success

### 成本
- 本轮验证合计约 46.8k token ≈ 0.12 元（含一次诊断调用 909）
- `run_eval` 新增 `--estimate`（只估算不发请求）与 `--max-tokens`（覆盖预算），估价口径：输入 2 元/M、输出 8 元/M、输出占 10%、实际消耗取预算 0.8
