"""
工具函数模块
提供配置加载、日志记录等通用功能
"""

import os
import copy
import yaml
import logging
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class Config:
    """Configuration manager."""

    def __init__(self, config_path: str = "configs/config.yaml"):
        self.project_root = Path(__file__).resolve().parents[2]
        raw_config_path = Path(config_path)
        self.config_path = raw_config_path if raw_config_path.is_absolute() else self.project_root / raw_config_path
        self.config = self._load_config()
        self._setup_paths()

    def _read_raw_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        return config if isinstance(config, dict) else {}

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML config file."""
        return self._apply_env_overrides(self._read_raw_config())

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply selected environment variable overrides."""
        mapping = {
            'LOG_DATASET': 'data.dataset',
            'LOG_SPLIT_MODE': 'data.split_mode',
            'LOG_SEQUENCE_LENGTH': 'data.sequence_length',
            'LOG_TEMP_SEQUENCE_LENGTH': 'data.temporal_sequence_length',
            'LOG_STAT_SEQUENCE_LENGTH': 'data.statistical_sequence_length',
            'LOG_TRAIN_RATIO': 'data.train_ratio',
            'LOG_SOURCE_FILTER_PROFILE': 'data.source_filter_profile',
            'LOG_RAG_CASE_FILE': 'rag.case_base.file',
            'LOG_RAG_INDEX_FILE': 'rag.case_base.index_file',
        }
        for env_key, cfg_key in mapping.items():
            raw = os.getenv(env_key)
            if raw in (None, ''):
                continue
            keys = cfg_key.split('.')
            cur = config
            for key in keys[:-1]:
                cur = cur.setdefault(key, {})
            old = cur.get(keys[-1])
            if isinstance(old, bool):
                value = str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}
            elif isinstance(old, int) and not isinstance(old, bool):
                value = int(raw)
            elif isinstance(old, float):
                value = float(raw)
            else:
                value = raw
            cur[keys[-1]] = value
        return config

    def _set_nested(self, payload: Dict[str, Any], key: str, value: Any):
        keys = key.split('.')
        cur = payload
        for part in keys[:-1]:
            child = cur.get(part)
            if not isinstance(child, dict):
                child = {}
                cur[part] = child
            cur = child
        cur[keys[-1]] = value

    def update_config(self, updates: Dict[str, Any], persist: bool = False):
        raw_config = self._read_raw_config()
        for key, value in (updates or {}).items():
            self._set_nested(raw_config, str(key), copy.deepcopy(value))
        if persist:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(raw_config, f, allow_unicode=True, sort_keys=False)
        self.config = self._apply_env_overrides(copy.deepcopy(raw_config))
        self._setup_paths()
        return self.config

    def reload(self):
        self.config = self._load_config()
        self._setup_paths()
        return self.config

    def _is_configured_path_key(self, key: str) -> bool:
        if key.startswith('paths.'):
            return True
        return key in {
            'logging.file',
            'rag.case_base.file',
            'rag.case_base.index_file',
        }

    def _resolve_path(self, value):
        if value in (None, ''):
            return value
        path = Path(value)
        if path.is_absolute():
            return str(path)
        return str((self.project_root / path).resolve())

    def _setup_paths(self):
        """Create configured directories under project root."""
        paths = self.config.get('paths', {})
        for category in paths.values():
            if isinstance(category, dict):
                for item in category.values():
                    Path(self._resolve_path(item)).mkdir(parents=True, exist_ok=True)
            else:
                Path(self._resolve_path(category)).mkdir(parents=True, exist_ok=True)

    def get(self, key: str, default=None):
        """Get config value; resolve path keys against project root."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        if value is None:
            return default
        if self._is_configured_path_key(key):
            return self._resolve_path(value)
        return value

    def __getitem__(self, key):
        """Dictionary-style access."""
        return self.get(key)


class Logger:
    """日志管理类"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str, config: Config = None) -> logging.Logger:
        """
        获取logger实例
        
        Args:
            name: logger名称
            config: 配置对象
        
        Returns:
            logger实例
        """
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)
        logger.propagate = False

        if config:
            level = config.get('logging.level', 'INFO')
            log_format = config.get('logging.format')
            log_file = config.get('logging.file')
        else:
            level = 'INFO'
            log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            log_file = None

        logger.setLevel(getattr(logging, level))

        # Streamlit 重跑会重新初始化 Logger 类缓存，但 logging 全局 logger 仍保留旧 handler。
        # 这里先清空，避免控制台日志重复输出（看起来像“同一步骤执行两次”）。
        if logger.handlers:
            logger.handlers.clear()

        # 控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level))
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件handler
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(getattr(logging, level))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        cls._loggers[name] = logger
        return logger


def load_env():
    """加载环境变量"""
    load_dotenv()
    return {
        'deepseek_api_key': os.getenv('DEEPSEEK_API_KEY'),
        'deepseek_base_url': os.getenv('DEEPSEEK_BASE_URL'),
        'qwen_api_key': os.getenv('QWEN_API_KEY'),
        'openai_api_key': os.getenv('OPENAI_API_KEY'),
        'hf_token': os.getenv('HF_TOKEN'),
    }


def set_random_seed(seed: int = 42):
    """
    设置随机种子以保证实验可复现
    
    Args:
        seed: 随机种子
    """
    import random
    import numpy as np
    import torch
    
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def get_device():
    """
    获取可用的计算设备
    
    Returns:
        torch.device
    """
    import torch
    return torch.device('cuda' if torch.cuda.is_available() else 'cpu')


if __name__ == "__main__":
    # 测试配置加载
    config = Config()
    print("配置加载成功!")
    print(f"数据集: {config.get('data.dataset')}")
    print(f"Bi-LSTM隐藏层大小: {config.get('models.bilstm.hidden_size')}")
    
    # 测试日志
    logger = Logger.get_logger('test', config)
    logger.info("日志系统测试")
    logger.debug("这是debug信息")
    logger.warning("这是warning信息")
