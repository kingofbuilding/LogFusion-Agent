"""
日志采集模块：
1. 采集 Linux 系统日志（syslog/messages/auth.log/secure）
2. 采集 Web 服务器日志（nginx/apache access/error）
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Iterable, List

from src.utils import Config, Logger


class LogCollector:
    """Linux 与 Web 日志采集器。"""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.raw_dir = Path(config.get("paths.data.raw"))
        self.max_lines_per_file = int(config.get("collector.max_lines_per_file", 200000))

    def _expand_patterns(self, patterns: Iterable[str]) -> List[Path]:
        """展开路径通配符并去重。"""
        paths = []
        for pat in patterns:
            for p in glob.glob(str(pat)):
                pp = Path(p)
                if pp.exists() and pp.is_file():
                    paths.append(pp)
        # 保持顺序去重
        seen = set()
        dedup = []
        for p in paths:
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                dedup.append(p)
        return dedup

    def _merge_logs(self, files: List[Path], out_file: Path) -> int:
        """合并多份日志到单一输出文件。"""
        out_file.parent.mkdir(parents=True, exist_ok=True)
        total_lines = 0
        with open(out_file, "w", encoding="utf-8", errors="ignore") as wf:
            for f in files:
                line_count = 0
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as rf:
                        for line in rf:
                            line = line.rstrip("\n")
                            if not line.strip():
                                continue
                            wf.write(line + "\n")
                            line_count += 1
                            total_lines += 1
                            if line_count >= self.max_lines_per_file:
                                break
                except Exception as e:
                    self.logger.warning(f"读取文件失败，跳过: {f}, err={e}")
                    continue
                self.logger.info(f"已采集 {f} -> {line_count} 行")
        return total_lines

    def collect_linux(self, extra_patterns: Iterable[str] | None = None) -> Path:
        """采集 Linux 系统日志。"""
        default_patterns = self.config.get(
            "collector.linux_patterns",
            [
                "/var/log/syslog",
                "/var/log/messages",
                "/var/log/auth.log",
                "/var/log/secure",
                "/var/log/kern.log",
                "data/raw/linux/source/*.log",
                "data/raw/linux/source/*.txt",
            ],
        )
        patterns = list(default_patterns) + list(extra_patterns or [])
        files = self._expand_patterns(patterns)
        out_file = self.raw_dir / "linux" / "linux.log"
        if not files:
            self.logger.warning("未发现 Linux 日志源文件。")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.touch(exist_ok=True)
            return out_file
        lines = self._merge_logs(files, out_file)
        self.logger.info(f"Linux 日志采集完成，输出: {out_file}, 总行数={lines}")
        return out_file

    def collect_web(self, extra_patterns: Iterable[str] | None = None) -> Path:
        """采集 Web 服务器日志。"""
        default_patterns = self.config.get(
            "collector.web_patterns",
            [
                "/var/log/nginx/access.log",
                "/var/log/nginx/error.log",
                "/var/log/apache2/access.log",
                "/var/log/apache2/error.log",
                "/var/log/httpd/access_log",
                "/var/log/httpd/error_log",
                "data/raw/web/source/*.log",
                "data/raw/web/source/*.txt",
            ],
        )
        patterns = list(default_patterns) + list(extra_patterns or [])
        files = self._expand_patterns(patterns)
        out_file = self.raw_dir / "web" / "web.log"
        if not files:
            self.logger.warning("未发现 Web 日志源文件。")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.touch(exist_ok=True)
            return out_file
        lines = self._merge_logs(files, out_file)
        self.logger.info(f"Web 日志采集完成，输出: {out_file}, 总行数={lines}")
        return out_file


def main():
    """命令行采集入口。"""
    config = Config()
    collector = LogCollector(config)

    mode = str(config.get("collector.mode", "linux")).lower()
    if mode == "linux":
        path = collector.collect_linux()
    elif mode == "web":
        path = collector.collect_web()
    else:
        linux_path = collector.collect_linux()
        web_path = collector.collect_web()
        print(f"Linux: {linux_path}")
        print(f"Web: {web_path}")
        return

    print(f"日志采集完成: {path}")


if __name__ == "__main__":
    main()
