from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from benchmarks.runners.run_bgl_public import main as run_bgl
from benchmarks.runners.run_hdfs_public import main as run_hdfs


def main():
    hdfs_csv, hdfs_json = run_hdfs()
    bgl_csv, bgl_json = run_bgl()
    out_dir = Path("outputs/reports/public_benchmarks")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    merged_csv = out_dir / f"public_benchmark_all_{ts}.csv"
    merged_json = out_dir / f"public_benchmark_all_{ts}.json"
    frames = [pd.read_csv(hdfs_csv), pd.read_csv(bgl_csv)]
    merged = pd.concat(frames, ignore_index=True)
    merged.to_csv(merged_csv, index=False, encoding="utf-8-sig")
    merged_json.write_text(json.dumps({"csv_files": [str(hdfs_csv), str(bgl_csv)], "rows": merged.to_dict(orient="records")}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Merged benchmark results saved to: {merged_csv}")
    return merged_csv, merged_json


if __name__ == "__main__":
    main()
