"""
Drain3-based log parser.
Convert raw logs into templates and template ids.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import Config, Logger


class DrainParser:
    """Log template parser."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)

        drain_config = TemplateMinerConfig()
        drain_config.drain_depth = int(config.get("drain.depth", 4))
        drain_config.drain_sim_th = float(config.get("drain.sim_th", 0.4))
        drain_config.drain_max_children = int(config.get("drain.max_children", 100))
        self.template_miner = TemplateMiner(config=drain_config)
        self.patterns = [
            ("TIMESTAMP", r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b"),
            ("MIXED_ID", r"\b\d+(?:-\d+){2,}(?:\.\d+){1,}\b"),
            ("IP", r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            ("UUID", r"\b[0-9a-fA-F]{8}\-(?:[0-9a-fA-F]{4}\-){3}[0-9a-fA-F]{12}\b"),
            ("HEXID", r"\b(?:0x)?[0-9a-fA-F]{8,}\b"),
            ("NODEID", r"(?<!<)\b[A-Za-z]+[A-Za-z0-9]*(?:[-_][A-Za-z0-9]+){1,}\b(?!>)"),
            ("COMPOSITE", r"\b\d+(?:[-_.]\d+){2,}\b"),
            ("VERSION", r"\b\d+(?:\.\d+){2,}\b"),
            ("NUM", r"\b\d+\b"),
        ]

    def preprocess_log(self, log_line: str) -> str:
        log_line = str(log_line or "")
        replacements = {
            "TIMESTAMP": "<TIMESTAMP>",
            "MIXED_ID": "<MIXED_ID>",
            "IP": "<IP>",
            "UUID": "<UUID>",
            "HEXID": "<HEXID>",
            "NODEID": "<NODEID>",
            "COMPOSITE": "<COMPOSITE>",
            "VERSION": "<VERSION>",
            "NUM": "<NUM>",
        }
        for name, pattern in self.patterns:
            log_line = re.sub(pattern, replacements[name], log_line)
        log_line = re.sub(r"\s+", " ", log_line)
        return log_line.strip()

    @staticmethod
    def _extract_timestamp(log_line: str):
        s = str(log_line or "")
        if not s:
            return None

        m = re.search(r"\b(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})\b", s)
        if m:
            try:
                return float(datetime.strptime(m.group(1).replace("T", " "), "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                pass

        m = re.search(r"\b(\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2})(?:\.\d+)?\b", s)
        if m:
            try:
                return float(datetime.strptime(m.group(1), "%Y-%m-%d-%H.%M.%S").timestamp())
            except Exception:
                pass

        m = re.match(r"^\s*\S+\s+(\d{10})(?:\s|$)", s)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass

        m = re.search(r"\b(\d{6})\s+(\d{6})\b", s)
        if m:
            try:
                return float(datetime.strptime(f"{m.group(1)} {m.group(2)}", "%y%m%d %H%M%S").timestamp())
            except Exception:
                pass

        return None

    def parse_log_line(self, log_line: str) -> dict:
        processed = self.preprocess_log(log_line)
        result = self.template_miner.add_log_message(processed)
        return {
            "raw_log": log_line,
            "timestamp": self._extract_timestamp(log_line),
            "processed_log": processed,
            "template": result["template_mined"],
            "template_id": result["cluster_id"],
            "cluster_size": result["cluster_size"],
        }

    def parse_log_file(self, input_file: Path, output_file: Path = None, source_name: str | None = None) -> pd.DataFrame:
        self.logger.info(f"start parse: {input_file}")
        rows = []
        with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = self.parse_log_line(line)
                    item["line_num"] = i
                    item["source_file"] = source_name or input_file.name
                    rows.append(item)
                except Exception as exc:
                    self.logger.warning(f"{input_file.name} line {i} parse failed: {exc}")

        df = pd.DataFrame(rows)
        if output_file is not None:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file, index=False)
            self.logger.info(f"saved parsed result: {output_file}")

        n_templates = df["template_id"].nunique() if len(df) else 0
        self.logger.info(f"parse finished, rows={len(df)}, templates={n_templates}")
        return df

    def parse_log_files(
        self,
        input_files: list[Path],
        output_file: Path = None,
        root_dir: Path | None = None,
    ) -> pd.DataFrame:
        rows = []
        global_line = 0
        for input_file in input_files:
            self.logger.info(f"start parse: {input_file}")
            with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = self.parse_log_line(line)
                        global_line += 1
                        item["line_num"] = global_line
                        if root_dir is not None:
                            try:
                                item["source_file"] = str(input_file.relative_to(root_dir)).replace("\\", "/")
                            except Exception:
                                item["source_file"] = input_file.name
                        else:
                            item["source_file"] = input_file.name
                        item["source_line_num"] = i
                        rows.append(item)
                    except Exception as exc:
                        self.logger.warning(f"{input_file.name} line {i} parse failed: {exc}")

        df = pd.DataFrame(rows)
        if output_file is not None:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file, index=False)
            self.logger.info(f"saved parsed result: {output_file}")

        n_templates = df["template_id"].nunique() if len(df) else 0
        self.logger.info(f"parse finished, rows={len(df)}, templates={n_templates}")
        return df

    def get_template_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        stats = (
            df.groupby(["template_id", "template"])
            .agg({"line_num": "count", "cluster_size": "first"})
            .reset_index()
        )
        stats.columns = ["template_id", "template", "occurrence", "cluster_size"]
        return stats.sort_values("occurrence", ascending=False)


def _find_input_logs(dataset_dir: Path, dataset: str):
    gather_dir = dataset_dir / "gather"
    if gather_dir.exists():
        return sorted(gather_dir.rglob("*.log"))

    candidates = [
        dataset_dir / f"{dataset}.log",
        dataset_dir / f"{dataset.upper()}.log",
        dataset_dir / f"{dataset.lower()}.log",
        dataset_dir / "HDFS.log",
        dataset_dir / "BGL.log",
    ]
    files = []
    seen = set()
    for path in candidates:
        if not path.exists():
            continue
        key = str(path.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        files.append(path)
    if files:
        return files
    return sorted(dataset_dir.rglob("*.log"))


def main():
    config = Config()
    parser = DrainParser(config)
    dataset = str(config.get("data.dataset", "hdfs"))

    raw_dir = Path(config.get("paths.data.raw"))
    processed_dir = Path(config.get("paths.data.processed"))
    dataset_dir = raw_dir / dataset
    input_files = _find_input_logs(dataset_dir, dataset)
    output_file = processed_dir / dataset / f"{dataset}_parsed.csv"

    if not input_files:
        print(f"error: no .log files found under {dataset_dir}")
        return

    print("=" * 60)
    print("Drain Log Parsing")
    print(f"input files: {len(input_files)}")
    print(f"output: {output_file}")
    print("=" * 60)

    if len(input_files) == 1:
        df = parser.parse_log_file(input_files[0], output_file)
    else:
        df = parser.parse_log_files(input_files, output_file, root_dir=dataset_dir)

    if len(df):
        print(parser.get_template_statistics(df).head(10).to_string(index=False))
    print("parse finished")


if __name__ == "__main__":
    main()
