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
