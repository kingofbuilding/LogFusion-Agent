"""Prepare a lightweight AIT-LDS v2 subset by extracting only labeled source logs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from remotezip import RemoteZip

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils import Config, Logger

BASE_URL = "https://zenodo.org/api/records/5789064/files/{subset}.zip/content"
EXTRA_FILES = ["dataset.yaml", "gather/attacker_0/logs/attacks.log"]


def extract_labeled_subset(subset: str, output_dir: Path, logger) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    url = BASE_URL.format(subset=subset)
    extracted: list[Path] = []
    with RemoteZip(url) as zf:
        names = zf.namelist()
        label_files = sorted(n for n in names if n.startswith("labels/") and n.endswith(".log"))
        targets = set(EXTRA_FILES)
        for label in label_files:
            targets.add(label)
            targets.add(f"gather/{label[len('labels/'):]}")

        for name in sorted(targets):
            if name not in names:
                logger.warning(f"archive entry missing: {name}")
                continue
            dest = output_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            extracted.append(dest)
            logger.info(f"extracted: {name}")
    return extracted


def main():
    parser = argparse.ArgumentParser(description="提取 AIT-LDS v2 子集中的带标签日志")
    parser.add_argument("--subset", default="russellmitchell", help="AIT-LDS v2 子集名")
    parser.add_argument("--output-dir", default="", help="输出目录，默认 data/raw/<subset>")
    args = parser.parse_args()

    cfg = Config()
    logger = Logger.get_logger("prepare_ait_lds", cfg)
    output_dir = Path(args.output_dir) if args.output_dir else Path(cfg.get("paths.data.raw")) / args.subset
    files = extract_labeled_subset(args.subset, output_dir, logger)
    print("=" * 70)
    print(f"AIT-LDS v2 子集提取完成: {args.subset}")
    print(f"输出目录: {output_dir}")
    print(f"提取文件数: {len(files)}")
    print("=" * 70)


if __name__ == "__main__":
    main()
