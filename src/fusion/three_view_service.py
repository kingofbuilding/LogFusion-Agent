"""
三视图统一评分服务：
1. 统计视图：Isolation Forest（频率/熵等统计特征）
2. 时序视图：Bi-LSTM + Attention（无模型时自动回退代理分数）
3. 语义视图：基于预训练语义向量（BGE）与风险锚点相似度评分
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import torch

from src.feature_extraction.semantic_features import SemanticFeatureExtractor
from src.fusion.log_domain import detect_log_domains
from src.feature_extraction.statistical_features import StatisticalFeatureExtractor, trim_statistical_window
from src.models.bilstm_attention import BiLSTMAttention
from src.models.isolation_forest_model import IsolationForestModel
from src.utils import Config, Logger, get_device


def _normalize(arr: np.ndarray) -> np.ndarray:
    """将数组归一化到 [0,1]。"""
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return arr
    span = float(arr.max() - arr.min())
    if span <= 1e-12:
        return np.zeros_like(arr, dtype=float)
    return (arr - arr.min()) / (span + 1e-8)


def _quantile_normalize(arr: np.ndarray, lo_q: float = 0.10, hi_q: float = 0.90) -> np.ndarray:
    """Use quantile range to keep scores from collapsing near zero on heavy-tailed inputs."""
    arr = np.asarray(arr, dtype=float)
    if arr.size == 0:
        return arr
    lo = float(np.quantile(arr, lo_q))
    hi = float(np.quantile(arr, hi_q))
    if hi - lo <= 1e-12:
        return _normalize(arr)
    return np.clip((arr - lo) / (hi - lo + 1e-8), 0.0, 1.0)




def _trim_view_window(arr: np.ndarray, target_len: int) -> np.ndarray:
    """Trim sequence inputs to the tail window for a specific view."""
    seq = np.asarray(arr)
    if seq.ndim != 2 or seq.size == 0:
        return seq
    target_len = int(max(1, min(int(target_len), seq.shape[1])))
    if target_len == seq.shape[1]:
        return seq
    return seq[:, -target_len:]

def _cosine_sim_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """计算余弦相似度矩阵，shape=(len(a), len(b))。"""
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    a_norm = np.linalg.norm(a, axis=1, keepdims=True) + 1e-8
    b_norm = np.linalg.norm(b, axis=1, keepdims=True).T + 1e-8
    return (a @ b.T) / (a_norm * b_norm)


SECURITY_HIGH_KEYWORDS = [
    "failed password",
    "authentication failure",
    "invalid user",
    "permission denied",
    "unauthorized",
    "sudo",
    "privilege escalation",
    "attack",
    "malware",
    "sql injection",
    "xss",
    "command and control",
    "reverse shell",
    "webshell",
    "brute force",
    "credential stuffing",
    "port scan",
    "lateral movement",
    "data exfiltration",
]

SYSTEM_HIGH_KEYWORDS = [
    "kernel panic",
    "segmentation fault",
    "disk failure",
    "i/o error",
    "io error",
    "out of memory",
    "oom",
    "service unavailable",
    "connection refused",
    "connection reset",
    "network unreachable",
    "broken pipe",
    "packet loss",
]

BGL_HIGH_KEYWORDS = [
    "ras kernel",
    "ras app",
    "generating core",
    "kernel fatal",
    "app fatal",
    "cache parity",
    "alignment exception",
    "double hummer",
    "ce sym",
    "node card",
]

HDFS_HIGH_KEYWORDS = [
    "packetresponder",
    "packet responder",
    "block transfer",
    "replication",
    "datanode",
    "namenode",
    "addstoredblock",
    "allocateblock",
    "receiving block",
    "served block",
    "block report",
    "write block",
    "replica",
    "lease recovery",
    "dfsclient",
]

MEDIUM_RISK_KEYWORDS = [
    "error",
    "exception",
    "timeout",
    "forbidden",
    "login",
    "session",
    "disconnect",
    "retry",
    "slow",
    "latency",
    "unavailable",
    "reset",
    "denied",
]


def _rule_semantic_prior(template_text: str) -> float:
    """Lightweight semantic prior used to stabilize embedding scores across log domains."""
    t = str(template_text).lower()
    if any(k in t for k in SECURITY_HIGH_KEYWORDS):
        return 0.88
    if any(k in t for k in SYSTEM_HIGH_KEYWORDS):
        return 0.82
    if any(k in t for k in HDFS_HIGH_KEYWORDS):
        return 0.78
    if any(k in t for k in MEDIUM_RISK_KEYWORDS):
        return 0.60
    return 0.35


def _build_dns_subscore(seq_raw_texts: Iterable[str]) -> np.ndarray:
    texts = [str(x or "") for x in seq_raw_texts]
    n = len(texts)
    if n == 0:
        return np.zeros((0,), dtype=float)
    out = np.zeros((n,), dtype=float)
    for i, text in enumerate(texts):
        lowered = text.lower()
        parts = [p.strip() for p in lowered.split('[seq]') if p.strip()]
        step_count = max(len(parts), 1)
        query = sum('query[' in p or 'query ' in p for p in parts) / step_count
        forwarded = sum('forwarded ' in p for p in parts) / step_count
        refused = sum('refused' in p or 'servfail' in p or 'nxdomain' in p for p in parts) / step_count
        long_token = 0.0
        for p in parts:
            tokens = [tok for tok in re.findall(r"[a-z0-9_.-]+", p) if tok]
            if any(len(tok) >= 24 for tok in tokens):
                long_token += 1.0
        long_token /= step_count
        mix = 1.0 if (query > 0 and ('reply ' in lowered or 'forwarded ' in lowered)) else 0.0
        out[i] = np.clip(np.mean([query, forwarded, refused, long_token, mix]), 0.0, 1.0)
    return out


class ThreeViewScoringService:
    """三视图评分服务。"""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.device = get_device()
        self.bilstm_runtime_device = self.device
        self.temporal_batch_size = int(config.get("models.bilstm.infer_batch_size", 256))
        self.stat_infer_batch_size = int(
            config.get("models.isolation_forest.infer_batch_size", 200000)
        )
        self.stat_proxy_blend = float(
            np.clip(config.get("models.isolation_forest.proxy_blend", 0.40), 0.0, 1.0)
        )
        self.stat_relative_blend = float(
            np.clip(config.get("models.isolation_forest.relative_blend", 0.18), 0.0, 1.0)
        )
        self.stat_fast_infer_enabled = bool(
            config.get("models.isolation_forest.fast_infer_enabled", False)
        )
        self.stat_skip_freq_over_sequences = int(
            config.get("models.isolation_forest.skip_frequency_over_sequences", 300000)
        )
        self.statistical_sequence_length = int(
            config.get("data.statistical_sequence_length", config.get("data.sequence_length", 50))
        )
        self.temporal_sequence_length = int(
            config.get("data.temporal_sequence_length", config.get("data.sequence_length", 50))
        )
        self.temporal_best_threshold = float(config.get("models.bilstm.default_threshold", 0.5))
        self.use_stat_parts = bool(config.get("models.xgboost.use_stat_parts", True))
        self.include_legacy_stat_in_meta = bool(config.get("models.xgboost.include_legacy_stat_in_meta", True))
        self.temporal_proxy_blend = float(config.get("models.bilstm.temporal_proxy_blend", 0.25))
        self.temporal_min_std = float(config.get("models.bilstm.temporal_min_std", 0.02))
        self.temporal_calibration_threshold_cap = float(
            config.get("models.bilstm.temporal_calibration_threshold_cap", 0.8)
        )
        self.temporal_low_std_prob_blend = float(
            config.get("models.bilstm.temporal_low_std_prob_blend", 0.7)
        )
        self.use_calibrated_temporal = bool(
            config.get("models.bilstm.use_calibrated_temporal_score", True)
        )
        self.semantic_distill_enabled = bool(
            config.get("features.semantic.distillation.enabled", True)
        )
        self.semantic_min_tokens = int(
            config.get("features.semantic.distillation.min_tokens", 4)
        )

        # 特征提取器
        self.stat_extractor = StatisticalFeatureExtractor(config)
        self.semantic_extractor = SemanticFeatureExtractor(config)

        # 模型加载
        self.if_model = self._load_iforest()
        self.bilstm_model = self._load_bilstm()

        # 语义风险锚点（用于向量相似度打分）
        self.semantic_anchor_texts = config.get(
            "features.semantic.risk_anchors",
            [
                "failed password for invalid user",
                "authentication failure detected",
                "multiple login attempts from suspicious ip",
                "permission denied access forbidden unauthorized",
                "privilege escalation sudo root abuse",
                "web attack sql injection attempt",
                "xss payload blocked by waf",
                "malware command and control traffic",
                "abnormal outbound connection exfiltration",
            ],
        )
        self.semantic_anchor_embeddings = self._build_anchor_embeddings()

    def _load_iforest(self) -> Optional[IsolationForestModel]:
        path = Path(self.config.get("paths.models.isolation_forest")) / "iforest_model.joblib"
        if not path.exists():
            self.logger.warning(f"未找到 IF 模型: {path}")
            return None
        model = IsolationForestModel(self.config)
        model.load_model(path)
        return model

    def _load_bilstm(self) -> Optional[BiLSTMAttention]:
        """加载 Bi-LSTM 模型；若不存在则回退时序代理分数。"""
        path = Path(self.config.get("paths.models.bilstm")) / "best_model.pth"
        if not path.exists():
            self.logger.info("未找到 Bi-LSTM 模型，时序分数将回退为代理分数。")
            return None
        try:
            try:
                ckpt = torch.load(path, map_location=self.device, weights_only=True)
            except TypeError:
                ckpt = torch.load(path, map_location=self.device)
            except Exception as e:
                self.logger.warning(f"weights_only=True fallback when loading Bi-LSTM checkpoint: {e}")
                ckpt = torch.load(path, map_location=self.device)
            self.temporal_best_threshold = float(ckpt.get("best_threshold", self.temporal_best_threshold))
            state = ckpt["model_state_dict"]
            vocab_size = int(state["embedding.weight"].shape[0])
            model = BiLSTMAttention(self.config, vocab_size=vocab_size).to(self.device)
            model.load_state_dict(state, strict=False)
            model.eval()
            self.logger.info(f"已加载 Bi-LSTM 模型: {path}")
            self.logger.info(f"Bi-LSTM temporal threshold={self.temporal_best_threshold:.4f}")
            return model
        except Exception as e:
            self.logger.warning(f"加载 Bi-LSTM 失败，回退代理时序分数: {e}")
            return None

    def _build_anchor_embeddings(self) -> np.ndarray:
        """生成风险锚点语义向量。"""
        try:
            emb = self.semantic_extractor.extract_embeddings(
                [str(x) for x in self.semantic_anchor_texts],
                show_progress=False,
            )
            if emb is None or len(emb) == 0:
                raise ValueError("anchor embedding empty")
            return np.asarray(emb, dtype=np.float32)
        except Exception as e:
            self.logger.warning(f"构建风险锚点向量失败，将使用规则语义分数: {e}")
            return np.empty((0, 0), dtype=np.float32)

    def _score_statistical(
        self,
        x_seq: np.ndarray,
        seq_timestamps: np.ndarray = None,
        seq_texts: Iterable[str] | None = None,
        raw_seq_texts: Iterable[str] | None = None,
    ) -> np.ndarray:
        """Statistical view: distribution and burst features -> calibrated anomaly score."""
        if self.if_model is None:
            # Fallback: keep a lightweight variance proxy when IF model is unavailable.
            return _normalize(np.var(x_seq.astype(float), axis=1))
        x_seq, seq_timestamps = trim_statistical_window(
            x_seq,
            seq_timestamps,
            self.statistical_sequence_length,
        )
        n = int(len(x_seq))
        expected_dim = int(getattr(self.if_model.model, "n_features_in_", 1))
        expected_dim = max(1, expected_dim)

        skip_frequency = bool(
            self.stat_fast_infer_enabled
            and n >= self.stat_skip_freq_over_sequences
            and "log_frequency" in list(self.stat_extractor.feature_names)
        )
        if skip_frequency:
            self.logger.info(
                f"Stat fast-infer for large input (n_seq={n}), skip log_frequency."
            )

        def _build_proxy_score(feature_bundle: Dict[str, np.ndarray]) -> np.ndarray:
            proxy_terms: List[np.ndarray] = []

            norm_entropy = feature_bundle.get("normalized_entropy")
            if norm_entropy is not None and len(norm_entropy):
                proxy_terms.append(np.clip(np.asarray(norm_entropy, dtype=float).reshape(-1), 0.0, 1.0))

            switch_rate = feature_bundle.get("switch_rate")
            if switch_rate is not None and len(switch_rate):
                proxy_terms.append(np.clip(np.asarray(switch_rate, dtype=float).reshape(-1), 0.0, 1.0))

            template_count = feature_bundle.get("template_count")
            if template_count is not None and len(template_count):
                proxy_terms.append(_quantile_normalize(np.asarray(template_count, dtype=float).reshape(-1)))

            dominant_ratio = feature_bundle.get("dominant_ratio")
            if dominant_ratio is not None and len(dominant_ratio):
                proxy_terms.append(
                    np.clip(1.0 - np.asarray(dominant_ratio, dtype=float).reshape(-1), 0.0, 1.0)
                )

            variance = feature_bundle.get("variance")
            if variance is not None and len(variance):
                proxy_terms.append(
                    _quantile_normalize(np.log1p(np.asarray(variance, dtype=float).reshape(-1)))
                )

            time_burstiness = feature_bundle.get("time_burstiness")
            if time_burstiness is not None and len(time_burstiness):
                proxy_terms.append(
                    _quantile_normalize(np.log1p(np.asarray(time_burstiness, dtype=float).reshape(-1)))
                )

            time_interval = feature_bundle.get("time_interval")
            if time_interval is not None and len(time_interval):
                interval_arr = np.asarray(time_interval, dtype=float)
                if interval_arr.ndim == 2 and interval_arr.shape[1] >= 1:
                    proxy_terms.append(_quantile_normalize(np.log1p(interval_arr[:, 0])))

            for key in [
                "auth_failure_ratio",
                "auth_success_ratio",
                "privileged_command_ratio",
                "web_probe_ratio",
                "suspicious_keyword_ratio",
                "auth_failure_density",
                "success_after_fail_chain",
                "session_after_fail_chain",
                "requests_per_ip",
                "unique_uri_per_ip",
                "failed_login_per_user",
                "unique_port_per_ip",
                "session_length",
                "mean_interval_per_ip",
            ]:
                feat = feature_bundle.get(key)
                if feat is not None and len(feat):
                    arr = np.asarray(feat, dtype=float).reshape(-1)
                    if key == "mean_interval_per_ip":
                        arr = _quantile_normalize(np.log1p(np.clip(arr, 0.0, None)))
                    else:
                        arr = np.clip(arr, 0.0, 1.0)
                    proxy_terms.append(arr)

            if not proxy_terms:
                return np.zeros((0,), dtype=float)

            return np.mean(np.column_stack(proxy_terms), axis=1)

        seq_text_arr = np.asarray(list(seq_texts), dtype=object) if seq_texts is not None else None
        raw_seq_text_arr = np.asarray(list(raw_seq_texts), dtype=object) if raw_seq_texts is not None else None

        def _extract_predict_chunk(
            x_chunk: np.ndarray,
            t_chunk: np.ndarray = None,
            s_chunk: np.ndarray | None = None,
            r_chunk: np.ndarray | None = None,
        ) -> np.ndarray:
            original_names = list(self.stat_extractor.feature_names)
            try:
                if skip_frequency:
                    names = [f for f in original_names if f != "log_frequency"]
                    if names:
                        self.stat_extractor.feature_names = names
                feature_bundle = self.stat_extractor.extract_all_features(
                    x_chunk,
                    seq_timestamps=t_chunk,
                    seq_texts=s_chunk,
                    seq_raw_texts=r_chunk,
                )
            finally:
                self.stat_extractor.feature_names = original_names

            feat = feature_bundle["combined"]

            if feat.shape[1] < expected_dim:
                pad = np.zeros((feat.shape[0], expected_dim - feat.shape[1]), dtype=feat.dtype)
                feat = np.hstack([feat, pad])
            elif feat.shape[1] > expected_dim:
                feat = feat[:, :expected_dim]

            if_score = self.if_model.predict_proba(feat)
            proxy_score = _build_proxy_score(feature_bundle)
            relative_score = self.if_model.predict_relative_anomaly(feat)
            if proxy_score.size != if_score.size:
                proxy_score = np.zeros_like(if_score)
            if relative_score.size != if_score.size:
                relative_score = np.zeros_like(if_score)
            w_proxy = float(np.clip(self.stat_proxy_blend, 0.0, 1.0))
            w_relative = float(np.clip(self.stat_relative_blend, 0.0, 1.0))
            base = max(0.0, 1.0 - w_proxy - w_relative)
            weight_sum = base + w_proxy + w_relative
            if weight_sum <= 1e-8:
                return if_score
            return np.clip(
                (base * if_score + w_proxy * proxy_score + w_relative * relative_score) / weight_sum,
                0.0,
                1.0,
            )

        batch_size = max(1, int(self.stat_infer_batch_size))
        if n <= batch_size:
            return _extract_predict_chunk(x_seq, seq_timestamps, seq_text_arr, raw_seq_text_arr)

        self.logger.info(
            f"Statistical scoring by chunks: n_seq={n}, batch_size={batch_size}, expected_dim={expected_dim}"
        )
        parts = []
        for start in range(0, n, batch_size):
            end = min(n, start + batch_size)
            t_chunk = None
            s_chunk = None
            r_chunk = None
            if isinstance(seq_timestamps, np.ndarray) and len(seq_timestamps) == n:
                t_chunk = seq_timestamps[start:end]
            if seq_text_arr is not None and len(seq_text_arr) == n:
                s_chunk = seq_text_arr[start:end]
            if raw_seq_text_arr is not None and len(raw_seq_text_arr) == n:
                r_chunk = raw_seq_text_arr[start:end]
            parts.append(_extract_predict_chunk(x_seq[start:end], t_chunk, s_chunk, r_chunk))
        return np.concatenate(parts, axis=0) if parts else np.array([], dtype=float)

    @staticmethod
    def _temporal_proxy_score(x_seq: np.ndarray) -> np.ndarray:
        """快速时序代理分数：序列内模板跳变强度。"""
        arr = np.asarray(x_seq)
        if arr.ndim != 2 or arr.size == 0:
            n = int(arr.shape[0]) if arr.ndim >= 1 else 0
            return np.zeros((n,), dtype=float)
        if arr.shape[1] <= 1:
            return np.zeros((arr.shape[0],), dtype=float)
        diff = np.abs(np.diff(arr.astype(np.float32), axis=1))
        return _normalize(np.mean(diff, axis=1))

    def _score_temporal(self, x_seq: np.ndarray) -> np.ndarray:
        """
        时序视图：
        - 有 Bi-LSTM：分批推理并做阈值校准
        - 无 Bi-LSTM：回退代理分数
        """
        x_seq = _trim_view_window(x_seq, self.temporal_sequence_length)
        proxy = self._temporal_proxy_score(x_seq)
        if self.bilstm_model is None:
            return proxy

        vocab_size = int(self.bilstm_model.embedding.num_embeddings)
        x_safe = x_seq.astype(np.int64).copy()
        x_safe[(x_safe < 0) | (x_safe >= vocab_size)] = 0

        def _infer(device: torch.device) -> np.ndarray:
            self.bilstm_runtime_device = device
            self.bilstm_model.to(device)
            self.bilstm_model.eval()
            prob_parts = []
            with torch.no_grad():
                for i in range(0, len(x_safe), self.temporal_batch_size):
                    batch = torch.LongTensor(x_safe[i : i + self.temporal_batch_size]).to(device)
                    logits, _ = self.bilstm_model(batch)
                    p = torch.sigmoid(logits.squeeze(-1)).detach().cpu().numpy()
                    prob_parts.append(p)
            return np.concatenate(prob_parts, axis=0) if prob_parts else np.array([], dtype=float)

        try:
            prob = _infer(self.device)
        except torch.OutOfMemoryError:
            self.logger.warning("Bi-LSTM 时序推理触发 CUDA OOM，自动回退 CPU 分批推理。")
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            prob = _infer(torch.device("cpu"))
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                self.logger.warning("Bi-LSTM 时序推理内存不足，自动回退 CPU 分批推理。")
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                prob = _infer(torch.device("cpu"))
            else:
                raise

        prob = np.asarray(prob, dtype=float)
        if prob.size == 0:
            return proxy

        if not self.use_calibrated_temporal:
            # 直接返回 sigmoid 概率，避免对不同数据集/不同批次分别做 min-max，
            # 否则时序分的绝对尺度会漂移，导致融合与跨数据集评估失真。
            return np.clip(prob, 0.0, 1.0)

        raw_thr = float(self.temporal_best_threshold)
        thr_cap = float(np.clip(self.temporal_calibration_threshold_cap, 0.5, 0.99))
        thr = float(np.clip(min(raw_thr, thr_cap), 1e-3, 1 - 1e-3))
        if raw_thr > thr_cap + 1e-6:
            self.logger.info(
                f"Temporal threshold capped from {raw_thr:.4f} to {thr:.4f} to preserve score spread."
            )
        calibrated = np.clip((prob - thr) / (1.0 - thr + 1e-8), 0.0, 1.0)

        blend = float(np.clip(self.temporal_proxy_blend, 0.0, 1.0))
        cal_std = float(np.std(calibrated))
        if cal_std < self.temporal_min_std:
            prob_norm = _normalize(prob)
            prob_blend = float(np.clip(self.temporal_low_std_prob_blend, 0.0, 1.0))
            out = prob_blend * prob_norm + (1.0 - prob_blend) * proxy
            self.logger.info(
                f"Temporal score std too small ({cal_std:.4f}), fallback to normalized prob blend={prob_blend:.2f}"
            )
            return np.clip(out, 0.0, 1.0)

        out = (1.0 - blend) * calibrated + blend * proxy
        return np.clip(out, 0.0, 1.0)

    def get_attention_weights(self, sequence: np.ndarray) -> Optional[np.ndarray]:
        """返回单条序列 Attention 权重。"""
        if self.bilstm_model is None or sequence is None or len(sequence) == 0:
            return None
        vocab_size = int(self.bilstm_model.embedding.num_embeddings)
        s = sequence.reshape(1, -1).astype(np.int64).copy()
        s[(s < 0) | (s >= vocab_size)] = 0
        with torch.no_grad():
            x = torch.LongTensor(s).to(self.bilstm_runtime_device)
            _, attn = self.bilstm_model(x)
            return attn.squeeze(0).detach().cpu().numpy()

    def _score_semantic(self, template_texts: Iterable[str]) -> np.ndarray:
        """
        语义视图：
        1) 使用 BGE(或回退哈希向量)提取模板语义向量
        2) 与风险锚点计算余弦相似度，得到连续风险分
        3) 用规则先验做轻微融合，保证在纯离线情况下也可解释
        """
        texts = [str(t) for t in template_texts]
        if len(texts) == 0:
            return np.array([], dtype=float)
        if self.semantic_distill_enabled:
            texts = [
                self._distill_for_semantic(t) if self._needs_semantic_distill(t) else str(t).lower()
                for t in texts
            ]

        # 去重后编码，避免重复模板重复推理
        uniq, inv = np.unique(np.asarray(texts, dtype=object), return_inverse=True)
        emb_uniq = self.semantic_extractor.extract_embeddings(uniq.tolist(), show_progress=False)
        emb_all = np.asarray(emb_uniq, dtype=np.float32)[inv]

        # 向量语义分（与风险锚点最大相似度）
        if self.semantic_anchor_embeddings.size > 0:
            sim = _cosine_sim_matrix(emb_all, self.semantic_anchor_embeddings)
            sim_score = np.max(sim, axis=1)
            sim_score = np.clip((sim_score + 1.0) / 2.0, 0.0, 1.0)
        else:
            sim_score = np.zeros(len(texts), dtype=float)

        # 规则先验分
        prior_score = np.array([_rule_semantic_prior(t) for t in texts], dtype=float)

        # 融合：语义向量为主，规则先验为辅
        sem_score = 0.8 * sim_score + 0.2 * prior_score
        return np.clip(sem_score, 0.0, 1.0)

    def _distill_for_semantic(self, text: str) -> str:
        """Reduce noisy fields before embedding to improve semantic clustering."""
        t = str(text).strip().lower()
        if not t:
            return "empty log event"

        patterns = [
            (r"\b\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\b", " <TIME> "),
            (r"\b\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d+\b", " <TIME> "),
            (r"\b\d{1,3}(?:\.\d{1,3}){3}\b", " <IP> "),
            (r"\b[a-f0-9]{8,}(?:-[a-f0-9]{4,})+\b", " <ID> "),
            (r"\bblk_-?\d+\b", " <BLOCK> "),
            (r"\b(?:pid|tid|port|uid|gid|node|disk|host)=\S+\b", " <KV> "),
            (r"\b\d+\b", " <NUM> "),
        ]
        for pat, rep in patterns:
            t = re.sub(pat, rep, t)

        t = re.sub(r"[^a-z0-9_<>\s]+", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        if not t:
            return "empty log event"
        if len(t.split()) < self.semantic_min_tokens:
            t = f"event {t}"
        return t

    @staticmethod
    def _needs_semantic_distill(text: str) -> bool:
        raw = str(text)
        if len(raw) >= 80:
            return True
        if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", raw):
            return True
        if re.search(r"\b\d{4}-\d{2}-\d{2}[ t]\d{2}:\d{2}:\d{2}", raw, re.IGNORECASE):
            return True
        digits = sum(ch.isdigit() for ch in raw)
        return digits >= max(6, int(0.25 * max(1, len(raw))))

    def _compute_stat_subscores(
        self,
        x_seq: np.ndarray,
        seq_timestamps: np.ndarray = None,
        seq_texts: Optional[Iterable[str]] = None,
        raw_seq_texts: Optional[Iterable[str]] = None,
    ) -> Dict[str, np.ndarray]:
        x_stat, t_stat = trim_statistical_window(x_seq, seq_timestamps, self.statistical_sequence_length)
        seq_texts = list(seq_texts) if seq_texts is not None else []
        raw_seq_texts = list(raw_seq_texts) if raw_seq_texts is not None else list(seq_texts)
        bundle = self.stat_extractor.extract_all_features(
            x_stat,
            seq_timestamps=t_stat,
            seq_texts=seq_texts,
            seq_raw_texts=raw_seq_texts,
        )

        def _flat(name: str) -> np.ndarray:
            arr = bundle.get(name)
            if arr is None:
                return np.zeros((len(x_stat),), dtype=float)
            arr = np.asarray(arr, dtype=float).reshape(len(x_stat), -1)
            return arr[:, 0]

        dist_terms = [
            np.clip(_flat('normalized_entropy'), 0.0, 1.0),
            np.clip(_flat('switch_rate'), 0.0, 1.0),
            _quantile_normalize(_flat('template_count')),
            np.clip(1.0 - _flat('dominant_ratio'), 0.0, 1.0),
            _quantile_normalize(np.log1p(np.clip(_flat('variance'), 0.0, None))),
            _quantile_normalize(np.log1p(np.clip(_flat('time_burstiness'), 0.0, None))),
        ]
        time_interval = bundle.get('time_interval')
        if time_interval is not None:
            tia = np.asarray(time_interval, dtype=float)
            if tia.ndim == 2 and tia.shape[1] >= 1:
                dist_terms.append(_quantile_normalize(np.log1p(np.clip(tia[:, 0], 0.0, None))))
        stat_dist = np.mean(np.column_stack(dist_terms), axis=1) if dist_terms else np.zeros((len(x_stat),), dtype=float)

        auth_terms = []
        for key in ['auth_failure_ratio', 'auth_success_ratio', 'auth_failure_density', 'success_after_fail_chain', 'session_after_fail_chain', 'failed_login_per_user']:
            arr = bundle.get(key)
            if arr is not None:
                auth_terms.append(np.clip(np.asarray(arr, dtype=float).reshape(-1), 0.0, 1.0))
        stat_auth = np.mean(np.column_stack(auth_terms), axis=1) if auth_terms else np.zeros((len(x_stat),), dtype=float)

        web_terms = []
        for key in ['web_probe_ratio', 'suspicious_keyword_ratio', 'unique_uri_per_ip', 'requests_per_ip']:
            arr = bundle.get(key)
            if arr is not None:
                web_terms.append(np.clip(np.asarray(arr, dtype=float).reshape(-1), 0.0, 1.0))
        stat_web = np.mean(np.column_stack(web_terms), axis=1) if web_terms else np.zeros((len(x_stat),), dtype=float)

        dns_source = raw_seq_texts if raw_seq_texts is not None else seq_texts
        stat_dns = _build_dns_subscore(dns_source)

        return {
            'stat_dist_score': np.clip(stat_dist, 0.0, 1.0),
            'stat_auth_score': np.clip(stat_auth, 0.0, 1.0),
            'stat_web_score': np.clip(stat_web, 0.0, 1.0),
            'stat_dns_score': np.clip(stat_dns, 0.0, 1.0),
        }


    def score(
        self,
        x_seq: np.ndarray,
        template_texts: List[str],
        seq_timestamps: np.ndarray = None,
        raw_seq_texts: Optional[Iterable[str]] = None,
    ) -> Dict[str, np.ndarray]:
        """Return per-view scores and fusion meta features."""
        if len(x_seq) == 0:
            empty = np.array([], dtype=float)
            return {
                "stat_scores": empty,
                "temporal_scores": empty,
                "semantic_scores": empty,
                "stat_dist_scores": empty,
                "stat_auth_scores": empty,
                "stat_web_scores": empty,
                "stat_dns_scores": empty,
                "meta_features": np.empty((0, 7 if self.include_legacy_stat_in_meta and self.use_stat_parts else 6 if self.use_stat_parts else 3), dtype=float),
            }

        stat = self._score_statistical(
            x_seq,
            seq_timestamps=seq_timestamps,
            seq_texts=template_texts,
            raw_seq_texts=raw_seq_texts,
        )
        temp = self._score_temporal(x_seq)
        sem = self._score_semantic(template_texts)

        stat_parts = self._compute_stat_subscores(
            x_seq,
            seq_timestamps=seq_timestamps,
            seq_texts=template_texts,
            raw_seq_texts=raw_seq_texts,
        )
        stat_dist = stat_parts["stat_dist_score"]
        stat_auth = stat_parts["stat_auth_score"]
        stat_web = stat_parts["stat_web_score"]
        stat_dns = stat_parts["stat_dns_score"]

        if self.use_stat_parts:
            if self.include_legacy_stat_in_meta:
                meta_features = np.column_stack([stat, temp, sem, stat_dist, stat_auth, stat_web, stat_dns])
            else:
                meta_features = np.column_stack([temp, sem, stat_dist, stat_auth, stat_web, stat_dns])
        else:
            meta_features = np.column_stack([stat, temp, sem])

        return {
            "stat_scores": stat,
            "temporal_scores": temp,
            "semantic_scores": sem,
            "stat_dist_scores": stat_dist,
            "stat_auth_scores": stat_auth,
            "stat_web_scores": stat_web,
            "stat_dns_scores": stat_dns,
            "meta_features": meta_features,
        }



