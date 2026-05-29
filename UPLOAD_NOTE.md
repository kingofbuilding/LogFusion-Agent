# GitHub 上传包说明

这个目录是从原项目中整理出的干净公开版本，只包含源码、配置模板、文档和必要示例数据。

未包含的本地内容包括：`data/raw/`、`data/processed/`、`data/vectors/`、`models/`、`outputs/`、`output/`、`reports/`、`.claude/`、真实 `.env`、缓存和大文件。

上传前建议再次执行：

```bash
git grep -n -E "sk-[A-Za-z0-9_-]{20,}|api[_-]?key|token|secret"
python main.py --help
python -m compileall main.py frontend src
```
