<claude-mem-context>
# Memory Context

# [log_analysis_system_complete] recent context, 2026-05-25 4:14pm GMT+8

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (13,276t read) | 95,595t work | 86% savings

### May 20, 2026
228 1:49p 🔵 安全日志分析系统主线协议与演示入口已明确分离
229 " 🔵 主程序串联了解析、特征、三视图评分、融合与 RAG 建库流程
230 " 🔵 RAG 案例库默认会从多安全子集自动增量扩充
231 " 🔵 前端默认启用按日志域自动阈值判警
232 " 🚨 AI 研判配置文件中存在明文 API 密钥
233 3:03p 🟣 新增 HeroSMS 测试短信提供方脚本
234 3:12p 🔴 HeroSMS CLI now supports no-command easy mode
235 " 🟣 Added Windows one-click launcher for HeroSMS easy mode
236 " 🔵 HeroSMS easy mode help text and syntax were validated
237 3:13p 🔵 HeroSMS easy-mode Chinese prompts are stored with mojibake
238 3:15p 🟣 Added desktop GUI for HeroSMS verification testing
239 " 🟣 Externalized HeroSMS option lists and added GUI launcher
240 3:16p ✅ HeroSMS GUI bundle was created and validated end-to-end
241 " 🔵 Localized HeroSMS preset labels are valid in external JSON
### May 21, 2026
329 10:41p ⚖️ DOCX workflow constrained to python-based editing
330 " 🔵 Guidance-record source documents were confirmed available
331 10:42p 🔵 PowerShell hex-inspection command is incompatible with local shell
332 10:43p 🔵 Guidance-record template is a legacy Word .doc file
333 " 🔵 Bundled Python runtime lacks Word COM support but local Office is installed
334 10:44p 🔵 Word COM conversion of legacy template hung for two minutes
335 10:45p 🔵 Headless Word automation stalled without producing a converted template
336 " 🔵 Ref-parameter Word Open call failed on PowerShell type coercion
337 10:46p 🔵 Minimal Word COM retry still hangs after killing existing WINWORD processes
338 10:47p 🔵 System Python can drive Word COM but no CLI `.doc` converters are installed
339 " 🔴 Legacy guidance-record template now converts reliably through Python Word COM
340 10:48p 🔵 Converted guidance-record template exposes exact fillable structure
341 " 🔵 Student, advisor, thesis, and experiment facts were extracted from the final manuscript
342 " 🔵 Project repository preserves a concrete thesis-development timeline for authentic guidance entries
343 10:49p ✅ Completed Zhou Yuxuan guidance-record form with thesis-based supervision timeline
344 " 🔵 Completed guidance-record document was structurally verified after generation
345 10:50p ✅ Completed guidance record was exported to PDF for layout verification
346 " ✅ Guidance-record PDF was rendered into page images for visual QA
### May 22, 2026
347 11:28p 🔵 Graduation defense source corpus confirmed on local machine
348 " ⚖️ PPT rebuild pipeline constrained to bundled presentation and render-QA workflow
349 11:29p 🔵 Security log analysis project already contains thesis and defense support artifacts
350 " 🔵 Bundled Python extraction failed on Chinese-named PPTX and DOCX paths
351 11:30p 🔵 Existing defense PPT narrative and metrics were fully recovered from the reference deck
352 " ⚖️ Chinese-path asset access switched to file discovery by glob and stable file metadata
353 " 🔵 DOCX and PDF source extraction remain unreliable despite successful file resolution
354 " 🔵 Poppler PDF renderer is unavailable in the defense deck workspace
365 11:31p ✅ Added reference-style RAG + LLM judge workflow figure asset
### May 25, 2026
460 1:09p 🔵 Log upload parsing crashes on missing 攻击子类 column
461 1:10p 🔵 攻击子类 initialization happens too late in build_view_df
S53 Fix Streamlit log upload crash caused by KeyError: “攻击子类” (May 25, 1:10 PM)
S52 Diagnose Streamlit log upload KeyError for missing “攻击子类” column (May 25, 1:10 PM)
462 1:11p 🔵 build_view_df constructs alert display and RAG enrichment columns
463 1:13p 🔴 Fixed missing 攻击子类 crash in detection view
464 " ✅ Documented 2026-05-25 log upload crash fix
465 2:38p 🔴 Verified log upload KeyError fix compiles
466 2:41p 🔵 Confirmed early attack hierarchy defaults in build_view_df
467 " 🔴 Hardened 攻击子类 fallback lookup
468 2:42p 🔴 Verified hardened 攻击子类 fallback compiles
S54 修复上传 log 文件后 Streamlit 检测页面报 `KeyError: '攻击子类'` 的崩溃问题，并说明验证与重启方式 (May 25, 2:43 PM)
**Investigated**: 定位到报错发生在 `frontend/runtime.py` 的 `build_view_df()` 中，上传日志后进入前端检测结果视图构建流程，RAG 辅助分类字段被拆分为“攻击大类/攻击子类”时，如果分类文本没有 `/` 分隔符，就可能只生成大类而没有子类。后续细粒度分类升级逻辑直接访问 `view_df.loc[upgrade_mask, "攻击子类"]`，因此触发 Pandas `KeyError`。同时检查到 Streamlit 缓存路径 `_get_cached_view_df(...)` 可能继续复用旧结果或旧模块。

**Learned**: 该问题不是日志文件本身格式错误，而是日志上传触发了 RAG 分类展示路径中的字段缺失边界情况。RAG 分类可能返回单级分类，例如 `异常登录`，不一定总是 `攻击大类/攻击子类` 格式。原代码虽然在函数末尾有兜底补列逻辑，但位置太晚，发生在崩溃访问之后，因此无法防止异常。要保证稳定，需要在视图构建早期初始化“攻击大类”和“攻击子类”，并在具体访问处也使用安全兜底读取。

**Completed**: `frontend/runtime.py` 已完成修复：在 `build_view_df()` 中提前初始化“攻击大类”和“攻击子类”列；同时将原本直接读取 `攻击子类` 的报错位置改为通过 `view_df.get("攻击子类", pd.Series("", index=view_df.index))` 安全兜底。`FUNCTION_UPDATE_LOG.md` 已记录本次变更。已执行 `python -m py_compile frontend/runtime.py`，编译检查通过。已告知需要重启 Streamlit 前端以加载新代码，并在仍复现旧错误时清除 Streamlit 缓存后重新上传日志。

**Next Steps**: 当前轨迹是让用户重启或刷新 Streamlit 前端，并用之前报错的 `.log` 文件重新上传验证页面是否正常渲染。如果仍出现同类错误，则下一步应检查 Streamlit 缓存、实际运行代码是否为已修改版本，以及是否还有其他列在 RAG/视图合并路径中存在类似缺失访问。


Access 96k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>