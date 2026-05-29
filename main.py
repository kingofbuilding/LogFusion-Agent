"""
主程序入口：提供命令行方式运行日志分析各阶段。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 将项目根目录加入导入路径
sys.path.insert(0, str(Path(__file__).parent))

from src.utils import Config, Logger


def collect_logs(mode: str, patterns: str = ""):
    """采集 Linux/Web 日志。"""
    from src.data_processing.log_collector import LogCollector

    cfg = Config()
    collector = LogCollector(cfg)
    extra = [x.strip() for x in patterns.split(",") if x.strip()] if patterns else []
    if mode == "linux":
        collector.collect_linux(extra)
    elif mode == "web":
        collector.collect_web(extra)
    else:
        collector.collect_linux(extra)
        collector.collect_web(extra)


def download_data():
    """下载数据集。"""
    from src.data_processing.download_data import main as download_main

    download_main()


def parse_logs():
    """解析原始日志。"""
    from src.data_processing.drain_parser import main as parse_main

    parse_main()


def extract_features():
    """提取统计与语义特征。"""
    from src.feature_extraction.extract_features import main as extract_main

    extract_main()


def train_bilstm():
    """训练 Bi-LSTM。"""
    from src.models.train_bilstm import main as bilstm_main

    bilstm_main()


def train_isolation_forest():
    """训练 Isolation Forest。"""
    from src.models.train_isolation_forest import main as if_main

    if_main()


def train_xgboost():
    """训练 XGBoost 融合模型。"""
    from src.fusion.train_xgboost import main as xgb_main

    xgb_main()


def train_deeplog():
    """?? DeepLog ?????"""
    from src.models.train_deeplog import main as deeplog_main

    deeplog_main()


def evaluate_views(datasets: str = ""):
    """评估单视图、融合与消融效果。"""
    from src.fusion.evaluate_views import main as eval_main

    dataset_list = [x.strip() for x in datasets.split(",") if x.strip()] if datasets else None
    eval_main(dataset_list)


def train_models(mode: str):
    """按指定模式训练模型。"""
    if mode == "bilstm":
        train_bilstm()
    elif mode == "iforest":
        train_isolation_forest()
    elif mode == "xgboost":
        train_xgboost()
    elif mode == "deeplog":
        train_deeplog()
    else:
        train_bilstm()
        train_isolation_forest()
        train_xgboost()


def run_frontend():
    """启动 Streamlit 前端。"""
    subprocess.run(["streamlit", "run", "frontend/app.py"], check=False)


def build_rag_case_base(force_rebuild: bool = False):
    """Build the active RAG case base using the configured security-log datasets by default."""
    import os
    from src.rag.attack_case_base import AttackCaseRAG

    cfg = Config()
    logger = Logger.get_logger("rag_builder", cfg)
    configured = cfg.get("rag.case_base.default_datasets", [])
    if isinstance(configured, str):
        datasets = [x.strip() for x in configured.split(",") if x.strip()]
    else:
        datasets = [str(x).strip() for x in configured if str(x).strip()]
    if not datasets:
        datasets = [str(cfg.get("data.dataset", "harrison")).strip()]

    old_dataset = os.environ.get("LOG_DATASET")
    total_added = 0
    per_dataset_added = {}
    logger.info(f"RAG auto-augment datasets: {', '.join(datasets)}")
    try:
        for ds in datasets:
            os.environ["LOG_DATASET"] = ds
            rag = AttackCaseRAG(Config())
            try:
                added = int(rag.augment_case_base_from_labeled_data())
                per_dataset_added[ds] = added
                total_added += added
                logger.info(f"RAG auto-augment dataset={ds}, added={added}")
            except Exception as exc:
                per_dataset_added[ds] = 0
                logger.warning(f"RAG auto-augment skipped dataset={ds}: {exc}")
        if old_dataset is None:
            os.environ["LOG_DATASET"] = datasets[-1]
        else:
            os.environ["LOG_DATASET"] = old_dataset
        rag = AttackCaseRAG(Config())
        rebuild_index = bool(force_rebuild or total_added > 0)
        index_count = rag.build_index(force_rebuild=rebuild_index)
        logger.info(f"RAG auto-augment summary={per_dataset_added}, total_added={total_added}, rebuild_index={rebuild_index}, index_count={index_count}")
    finally:
        if old_dataset is None:
            os.environ.pop("LOG_DATASET", None)
        else:
            os.environ["LOG_DATASET"] = old_dataset

def main():
    parser = argparse.ArgumentParser(
        description="安全日志分析助手（多视图融合可运行版）"
    )
    parser.add_argument("--download", action="store_true", help="下载数据集")
    parser.add_argument("--collect", action="store_true", help="采集 Linux/Web 日志")
    parser.add_argument(
        "--collect-mode",
        choices=["linux", "web", "all"],
        default="all",
        help="采集类型",
    )
    parser.add_argument(
        "--collect-patterns",
        type=str,
        default="",
        help="附加日志路径通配符，多个用逗号分隔",
    )
    parser.add_argument("--parse", action="store_true", help="解析原始日志")
    parser.add_argument("--extract", action="store_true", help="提取特征")
    parser.add_argument("--train", action="store_true", help="训练模型")
    parser.add_argument(
        "--train-mode",
        choices=["all", "bilstm", "iforest", "xgboost", "deeplog"],
        default="all",
        help="训练模型类型（默认 all）",
    )
    parser.add_argument("--frontend", action="store_true", help="启动前端页面")
    parser.add_argument("--evaluate-views", action="store_true", help="评估单视图、融合与消融效果")
    parser.add_argument("--eval-datasets", type=str, default="", help="待评估数据集，多个用逗号分隔，如 hdfs,bgl")
    parser.add_argument("--build-rag", action="store_true", help="构建 RAG 攻击案例库")
    parser.add_argument("--rag-force", action="store_true", help="强制重建 RAG 索引")
    parser.add_argument("--with-rag", action="store_true", help="训练完成后同时构建 RAG 案例库")
    parser.add_argument("--all", action="store_true", help="执行完整流程（解析→特征→训练）")
    args = parser.parse_args()

    config = Config()
    logger = Logger.get_logger("main", config)

    print("=" * 70)
    print("安全日志分析助手")
    print("=" * 70)

    if args.all:
        logger.info("执行完整流程：解析 -> 特征提取 -> 训练")
        parse_logs()
        extract_features()
        train_models(args.train_mode)
        if args.with_rag:
            build_rag_case_base(force_rebuild=bool(args.rag_force))
    elif args.download:
        download_data()
    elif args.collect:
        collect_logs(args.collect_mode, args.collect_patterns)
    elif args.parse:
        parse_logs()
    elif args.extract:
        extract_features()
    elif args.train:
        train_models(args.train_mode)
        if args.with_rag:
            build_rag_case_base(force_rebuild=bool(args.rag_force))
    elif args.frontend:
        run_frontend()
    elif args.evaluate_views:
        evaluate_views(args.eval_datasets)
    elif args.build_rag:
        build_rag_case_base(force_rebuild=bool(args.rag_force))
    else:
        parser.print_help()

    print("=" * 70)


if __name__ == "__main__":
    main()
