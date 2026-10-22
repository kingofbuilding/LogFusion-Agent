"""Rebuild the RAG case index offline.

Backends:
    tfidf   sparse TF-IDF vectors (default; no model needed)
    minilm  dense MiniLM embeddings from a local ONNX export (needs onnxruntime + tokenizers)

The published index used hash embeddings, which score related text around 0.05-0.15 and made
retrieval look broken. Both backends below are offline and deterministic.

Usage:
    python scripts/rebuild_rag_index.py
    python scripts/rebuild_rag_index.py --backend minilm --model-dir <path-to-all-MiniLM-L6-v2>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.agent.rag_index import build_minilm_index, build_tfidf_index, load_cases

CASES = ROOT / "data/rag/attack_cases.jsonl"
OUT_DIR = ROOT / "data/vectors"
FALLBACK_MINILM = Path(r"C:\Users\zhouyuxuan\.vscode\extensions\continue.continue-2.0.0-win32-x64\models\all-MiniLM-L6-v2")


def default_model_dir() -> Path | None:
    configured = os.getenv("MINILM_MODEL_DIR")
    if configured:
        return Path(configured)
    return FALLBACK_MINILM if FALLBACK_MINILM.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 RAG 案例索引（离线）")
    parser.add_argument("--backend", choices=["tfidf", "minilm"], default="tfidf")
    parser.add_argument("--model-dir", type=Path, default=None,
                        help="本地 MiniLM（ONNX）目录，默认取 MINILM_MODEL_DIR 或常见安装位置")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        print(f"未找到案例：{args.cases}")
        return 2
    if args.backend == "tfidf":
        summary = build_tfidf_index(cases, args.out)
    else:
        model_dir = args.model_dir or default_model_dir()
        if model_dir is None:
            print("未找到 MiniLM 模型目录；用 --model-dir 指定，或设置 MINILM_MODEL_DIR。")
            return 2
        summary = build_minilm_index(cases, args.out, Path(model_dir))
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
