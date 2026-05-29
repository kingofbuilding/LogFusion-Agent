"""
Public dataset downloader for this project.
Downloads selected Loghub datasets from Zenodo into data/raw/.
"""

from __future__ import annotations

import os
import sys
import tarfile
from pathlib import Path

import requests
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.utils import Config, Logger


class DataDownloader:
    """Download supported public log datasets."""

    DATASETS = {
        "hdfs": {
            "url": "https://zenodo.org/records/3227177/files/HDFS_1.tar.gz",
            "type": "tar.gz",
            "description": "HDFS dataset with labeled anomalies",
            "check_files": ["HDFS.log", "anomaly_label.csv"],
        },
        "bgl": {
            "url": "https://zenodo.org/records/3227177/files/BGL.tar.gz",
            "type": "tar.gz",
            "description": "BGL supercomputer logs",
            "check_files": ["BGL.log"],
        },
        "openstack": {
            "url": "https://zenodo.org/records/1492218/files/OpenStack.tar.gz",
            "type": "tar.gz",
            "description": "OpenStack logs from Loghub",
            "check_files": ["OpenStack_2k.log", "OpenStack_normal2.log", "OpenStack_abnormal.log"],
        },
        "hadoop": {
            "url": "https://zenodo.org/records/1492218/files/Hadoop.tar.gz",
            "type": "tar.gz",
            "description": "Hadoop application logs from Loghub",
            "check_files": ["Hadoop.log"],
        },
        "linux": {
            "url": "https://zenodo.org/records/1492218/files/Linux.tar.gz",
            "type": "tar.gz",
            "description": "Linux system logs from Loghub",
            "check_files": ["Linux.log"],
        },
        "ssh": {
            "url": "https://zenodo.org/records/1492218/files/SSH.tar.gz",
            "type": "tar.gz",
            "description": "SSH authentication logs from Loghub",
            "check_files": ["SSH.log"],
        },
        "zookeeper": {
            "url": "https://zenodo.org/records/1492218/files/Zookeeper.tar.gz",
            "type": "tar.gz",
            "description": "Zookeeper logs from Loghub",
            "check_files": ["Zookeeper.log"],
        },
        "healthapp": {
            "url": "https://zenodo.org/records/1492218/files/HealthApp.tar.gz",
            "type": "tar.gz",
            "description": "HealthApp mobile logs from Loghub",
            "check_files": ["HealthApp.log"],
        },
    }

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.data_dir = Path(config.get("paths.data.raw"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_file(self, url: str, filepath: Path) -> bool:
        try:
            self.logger.info(f"start download: {url}")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "wb") as f:
                if total_size <= 0:
                    f.write(response.content)
                else:
                    with tqdm(total=total_size, unit="B", unit_scale=True, desc=filepath.name) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if not chunk:
                                continue
                            f.write(chunk)
                            pbar.update(len(chunk))

            self.logger.info(f"download finished: {filepath}")
            return True
        except Exception as exc:
            self.logger.error(f"download failed: {url}, error={exc}")
            if filepath.exists():
                filepath.unlink()
            return False

    def extract_tar_gz(self, tar_path: Path, extract_dir: Path) -> bool:
        try:
            self.logger.info(f"extract archive: {tar_path}")
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=extract_dir)
            tar_path.unlink()
            self.logger.info(f"extract finished: {extract_dir}")
            return True
        except Exception as exc:
            self.logger.error(f"extract failed: {tar_path}, error={exc}")
            return False

    def _dataset_exists(self, dataset_name: str, dataset_dir: Path) -> bool:
        info = self.DATASETS[dataset_name]
        check_files = info.get("check_files", [])
        if check_files and any((dataset_dir / name).exists() for name in check_files):
            return True
        try:
            return any(dataset_dir.iterdir())
        except FileNotFoundError:
            return False

    def download_dataset(self, dataset_name: str) -> bool:
        if dataset_name not in self.DATASETS:
            self.logger.error(f"unsupported dataset: {dataset_name}")
            self.logger.info(f"supported datasets: {list(self.DATASETS.keys())}")
            return False

        dataset_info = self.DATASETS[dataset_name]
        dataset_dir = self.data_dir / dataset_name
        dataset_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"dataset: {dataset_info['description']}")
        if self._dataset_exists(dataset_name, dataset_dir):
            self.logger.info(f"dataset already exists: {dataset_dir}")
            return True

        archive_file = dataset_dir / f"{dataset_name}.tar.gz"
        if not self.download_file(dataset_info["url"], archive_file):
            return False
        if dataset_info["type"] == "tar.gz":
            if not self.extract_tar_gz(archive_file, dataset_dir):
                return False

        files = [f.name for f in dataset_dir.glob("*")]
        self.logger.info(f"dataset ready: {dataset_dir}")
        self.logger.info(f"files: {files}")
        return True

    def download_all(self):
        for dataset_name in self.DATASETS:
            self.logger.info("=" * 50)
            self.logger.info(f"download dataset: {dataset_name}")
            self.logger.info("=" * 50)
            self.download_dataset(dataset_name)


def main():
    config = Config()
    downloader = DataDownloader(config)
    dataset = str(config.get("data.dataset", "hdfs")).strip().lower()

    print("=" * 70)
    print("Log Dataset Downloader")
    print("=" * 70)
    print(f"dataset: {dataset}")
    print("source: Zenodo Loghub")
    print("record: https://zenodo.org/records/1492218")
    print(f"supported: {', '.join(DataDownloader.DATASETS.keys())}")
    print("-" * 70)

    success = downloader.download_dataset(dataset)

    print("=" * 70)
    if success:
        print("download completed")
        print(f"saved to: {config.get('paths.data.raw')}/{dataset}/")
    else:
        print("download failed")
        print("fallback: check network or download manually from Zenodo Loghub")
    print("=" * 70)


if __name__ == "__main__":
    main()
