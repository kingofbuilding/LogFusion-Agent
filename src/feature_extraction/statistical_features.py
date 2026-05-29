"""Statistical feature extraction for log-template sequences."""

from __future__ import annotations

import os
import re
import sys
from typing import Dict, Iterable, Tuple

SYSLOG_MONTHS = {m: i + 1 for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.utils import Config, Logger


def trim_statistical_window(
    sequences: np.ndarray,
    seq_timestamps: np.ndarray | None = None,
    statistical_sequence_length: int | None = None,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Trim statistical-view inputs to a tail window without changing sample alignment."""
    arr = np.asarray(sequences)
    if arr.ndim != 2 or arr.size == 0:
        return arr, seq_timestamps

    target_len = int(statistical_sequence_length or arr.shape[1])
    target_len = max(1, min(target_len, arr.shape[1]))
    if target_len == arr.shape[1]:
        return arr, seq_timestamps

    arr_trimmed = arr[:, -target_len:]
    ts_trimmed = seq_timestamps
    if isinstance(seq_timestamps, np.ndarray) and seq_timestamps.shape == arr.shape:
        ts_trimmed = seq_timestamps[:, -target_len:]
    return arr_trimmed, ts_trimmed


class StatisticalFeatureExtractor:
    """Extract sequence-level statistical features for anomaly scoring."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = Logger.get_logger(self.__class__.__name__, config)
        self.feature_names = config.get(
            'features.statistical',
            [
                'log_frequency',
                'entropy',
                'normalized_entropy',
                'template_count',
                'dominant_ratio',
                'repetition_ratio',
                'switch_rate',
                'top2_concentration',
                'param_variance',
                'time_interval',
                'time_burstiness',
                'auth_failure_ratio',
                'auth_success_ratio',
                'privileged_command_ratio',
                'web_probe_ratio',
                'suspicious_keyword_ratio',
                'auth_failure_density',
                'success_after_fail_chain',
                'session_after_fail_chain',
                'requests_per_ip',
                'unique_uri_per_ip',
                'failed_login_per_user',
                'unique_port_per_ip',
                'session_length',
                'mean_interval_per_ip',
            ],
        )
        self._auth_fail_re = re.compile(
            r"(failed password|authentication failure|invalid user|user unknown|check pass|maximum login attempts exceeded)",
            re.IGNORECASE,
        )
        self._auth_success_re = re.compile(
            r"(accepted password|accepted publickey|session opened for user|login successful|peer connection initiated)",
            re.IGNORECASE,
        )
        self._privileged_re = re.compile(
            r"(sudo| su |execve|setuid|setgid|chmod|chown|passwd|shadow|sudoers|root)",
            re.IGNORECASE,
        )
        self._web_probe_re = re.compile(
            r"(wpscan|nmap scripting engine|wp-login|/\.{2}/|/etc/passwd|ah01630|ah00687|union select|<script|multipart/form-data|shell\.php)",
            re.IGNORECASE,
        )
        self._suspicious_re = re.compile(
            r"(failed|denied|forbidden|unauthorized|error|exception|timeout|scan|probe|malware|attack|payload|drop|disconnect|tls error)",
            re.IGNORECASE,
        )
        self._ip_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        self._port_re = re.compile(r"(?:port\s+(\d{1,5})\b|client\s+(?:\d{1,3}\.){3}\d{1,3}:(\d{1,5})\b)", re.IGNORECASE)
        self._http_uri_re = re.compile(r'"(?:GET|POST|PUT|DELETE|HEAD|OPTIONS|PATCH)\s+([^\s"]+)\s+HTTP/[^"]+"', re.IGNORECASE)
        self._dns_target_patterns = [
            re.compile(r"query\[[A-Z]+\]\s+([^\s]+)\s+from\s+(?:\d{1,3}\.){3}\d{1,3}", re.IGNORECASE),
            re.compile(r"forwarded\s+([^\s]+)\s+to\s+(?:\d{1,3}\.){3}\d{1,3}", re.IGNORECASE),
            re.compile(r"reply\s+([^\s]+)\s+is\s+", re.IGNORECASE),
        ]
        self._syslog_time_re = re.compile(r"^(?:[a-z]{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})", re.IGNORECASE)
        self._user_patterns = [
            re.compile(r"for\s+(?:invalid\s+user\s+)?([a-zA-Z0-9_.-]+)", re.IGNORECASE),
            re.compile(r"user(?:name)?[=:\s]+([a-zA-Z0-9_.-]+)", re.IGNORECASE),
            re.compile(r"session opened for user\s+([a-zA-Z0-9_.-]+)", re.IGNORECASE),
            re.compile(r"ruser=([a-zA-Z0-9_.-]+)", re.IGNORECASE),
        ]

    @staticmethod
    def _build_count_matrix(sequences: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        arr = np.asarray(sequences, dtype=np.int64)
        if arr.ndim != 2 or arr.size == 0:
            n = int(arr.shape[0]) if arr.ndim >= 1 else 0
            return np.zeros((n, 0), dtype=np.float32), np.array([], dtype=np.int64)

        n, seq_len = arr.shape
        flat = arr.reshape(-1)
        template_list = np.unique(flat)
        col_idx = np.searchsorted(template_list, flat)
        row_idx = np.repeat(np.arange(n, dtype=np.int64), seq_len)
        count_matrix = np.zeros((n, len(template_list)), dtype=np.float32)
        np.add.at(count_matrix, (row_idx, col_idx), 1.0)
        return count_matrix, template_list

    def extract_frequency_features(self, sequences: np.ndarray, count_matrix: np.ndarray | None = None) -> np.ndarray:
        self.logger.info('extract frequency features...')
        if count_matrix is None:
            count_matrix, _ = self._build_count_matrix(sequences)
        return np.asarray(count_matrix, dtype=np.float32)

    def extract_entropy_features(self, sequences: np.ndarray, count_matrix: np.ndarray | None = None) -> np.ndarray:
        self.logger.info('extract entropy features...')
        if count_matrix is None:
            count_matrix, _ = self._build_count_matrix(sequences)
        if count_matrix.size == 0:
            n = int(np.asarray(sequences).shape[0]) if np.asarray(sequences).ndim >= 1 else 0
            return np.zeros((n, 1), dtype=np.float32)

        total = count_matrix.sum(axis=1, keepdims=True)
        total = np.where(total > 0, total, 1.0)
        probs = count_matrix / total
        with np.errstate(divide='ignore', invalid='ignore'):
            logp = np.zeros_like(probs, dtype=np.float32)
            mask = probs > 0
            logp[mask] = np.log2(probs[mask])
        ent = -(probs * logp).sum(axis=1, keepdims=True)
        return ent.astype(np.float32)

    def extract_normalized_entropy_features(self, sequences: np.ndarray, count_matrix: np.ndarray | None = None) -> np.ndarray:
        self.logger.info('extract normalized entropy features...')
        if count_matrix is None:
            count_matrix, _ = self._build_count_matrix(sequences)
        if count_matrix.size == 0:
            n = int(np.asarray(sequences).shape[0]) if np.asarray(sequences).ndim >= 1 else 0
            return np.zeros((n, 1), dtype=np.float32)

        ent = self.extract_entropy_features(sequences, count_matrix=count_matrix)
        unique_count = np.maximum((count_matrix > 0).sum(axis=1, keepdims=True).astype(np.float32), 1.0)
        denom = np.log2(np.maximum(unique_count, 2.0))
        denom = np.where(denom > 0, denom, 1.0)
        return np.clip(ent / denom, 0.0, 1.0).astype(np.float32)

    def extract_template_count_features(self, sequences: np.ndarray, count_matrix: np.ndarray | None = None) -> np.ndarray:
        self.logger.info('extract template-count features...')
        if count_matrix is None:
            count_matrix, _ = self._build_count_matrix(sequences)
        counts = (count_matrix > 0).sum(axis=1, keepdims=True)
        return counts.astype(np.float32)

    def extract_concentration_features(self, sequences: np.ndarray, count_matrix: np.ndarray | None = None) -> Dict[str, np.ndarray]:
        self.logger.info('extract concentration features...')
        if count_matrix is None:
            count_matrix, _ = self._build_count_matrix(sequences)
        if count_matrix.size == 0:
            n = int(np.asarray(sequences).shape[0]) if np.asarray(sequences).ndim >= 1 else 0
            zeros = np.zeros((n, 1), dtype=np.float32)
            return {
                'dominant_ratio': zeros,
                'repetition_ratio': zeros,
                'top2_concentration': zeros,
            }

        seq_len = float(np.asarray(sequences).shape[1]) if np.asarray(sequences).ndim == 2 else 1.0
        sorted_counts = -np.sort(-count_matrix, axis=1)
        dominant = (sorted_counts[:, :1] / max(seq_len, 1.0)).astype(np.float32)
        top2 = (sorted_counts[:, :2].sum(axis=1, keepdims=True) / max(seq_len, 1.0)).astype(np.float32)
        unique = (count_matrix > 0).sum(axis=1, keepdims=True).astype(np.float32)
        repetition = np.clip(1.0 - unique / max(seq_len, 1.0), 0.0, 1.0).astype(np.float32)
        return {
            'dominant_ratio': dominant,
            'repetition_ratio': repetition,
            'top2_concentration': top2,
        }

    def extract_switch_rate_features(self, sequences: np.ndarray) -> np.ndarray:
        self.logger.info('extract switch-rate features...')
        arr = np.asarray(sequences, dtype=np.int64)
        if arr.ndim != 2 or arr.size == 0:
            n = int(arr.shape[0]) if arr.ndim >= 1 else 0
            return np.zeros((n, 1), dtype=np.float32)
        if arr.shape[1] <= 1:
            return np.zeros((arr.shape[0], 1), dtype=np.float32)
        switches = (arr[:, 1:] != arr[:, :-1]).mean(axis=1, keepdims=True)
        return switches.astype(np.float32)

    def extract_variance_features(self, sequences: np.ndarray) -> np.ndarray:
        self.logger.info('extract variance features...')
        arr = np.asarray(sequences, dtype=np.float32)
        if arr.ndim != 2 or arr.size == 0:
            n = int(arr.shape[0]) if arr.ndim >= 1 else 0
            return np.zeros((n, 1), dtype=np.float32)
        return np.var(arr, axis=1, keepdims=True).astype(np.float32)

    def extract_time_interval_features(self, sequences: np.ndarray, seq_timestamps: np.ndarray | None = None) -> np.ndarray:
        self.logger.info('extract time-interval features...')
        seq_arr = np.asarray(sequences)
        if seq_arr.ndim != 2 or seq_arr.size == 0:
            n = int(seq_arr.shape[0]) if seq_arr.ndim >= 1 else 0
            return np.zeros((n, 3), dtype=np.float32)
        if seq_arr.shape[1] <= 1:
            return np.zeros((seq_arr.shape[0], 3), dtype=np.float32)

        use_ts = (
            seq_timestamps is not None
            and isinstance(seq_timestamps, np.ndarray)
            and seq_timestamps.shape == sequences.shape
        )
        if use_ts:
            diffs = np.diff(seq_timestamps.astype(np.float32), axis=1)
            diffs = np.clip(diffs, 0.0, None)
            abs_diffs = diffs
        else:
            diffs = np.diff(seq_arr.astype(np.float32), axis=1)
            abs_diffs = np.abs(diffs)

        mean_diff = np.mean(abs_diffs, axis=1)
        std_diff = np.std(diffs, axis=1)
        max_diff = np.max(abs_diffs, axis=1)
        return np.column_stack([mean_diff, std_diff, max_diff]).astype(np.float32)

    def extract_security_text_features(self, seq_texts: Iterable[str]) -> Dict[str, np.ndarray]:
        """Extract lightweight security-scene ratios from distilled/raw sequence texts."""
        texts = [str(x or "") for x in seq_texts]
        n = len(texts)
        if n == 0:
            zeros = np.zeros((0, 1), dtype=np.float32)
            return {
                'auth_failure_ratio': zeros,
                'auth_success_ratio': zeros,
                'privileged_command_ratio': zeros,
                'web_probe_ratio': zeros,
                'suspicious_keyword_ratio': zeros,
                'auth_failure_density': zeros,
                'success_after_fail_chain': zeros,
                'session_after_fail_chain': zeros,
            }

        fail = np.array([1.0 if self._auth_fail_re.search(t) else 0.0 for t in texts], dtype=np.float32).reshape(-1, 1)
        success = np.array([1.0 if self._auth_success_re.search(t) else 0.0 for t in texts], dtype=np.float32).reshape(-1, 1)
        privileged = np.array([1.0 if self._privileged_re.search(t) else 0.0 for t in texts], dtype=np.float32).reshape(-1, 1)
        web_probe = np.array([1.0 if self._web_probe_re.search(t) else 0.0 for t in texts], dtype=np.float32).reshape(-1, 1)

        suspicious_ratio = np.zeros((n, 1), dtype=np.float32)
        auth_failure_density = np.zeros((n, 1), dtype=np.float32)
        success_after_fail_chain = np.zeros((n, 1), dtype=np.float32)
        session_after_fail_chain = np.zeros((n, 1), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = re.findall(r"[a-zA-Z0-9_./:-]+", text.lower())
            token_count = max(len(tokens), 1)
            matched = sum(1 for tok in tokens if self._suspicious_re.search(tok))
            suspicious_ratio[i, 0] = float(matched) / float(token_count)

            parts = [p.strip() for p in text.lower().split('[seq]') if p.strip()]
            step_count = max(len(parts), 1)
            fail_flags = np.array([1.0 if self._auth_fail_re.search(p) else 0.0 for p in parts], dtype=np.float32)
            success_flags = np.array([1.0 if ('accepted password' in p or 'accepted publickey' in p or 'login successful' in p) else 0.0 for p in parts], dtype=np.float32)
            session_flags = np.array([1.0 if ('session opened for user' in p or 'peer connection initiated' in p) else 0.0 for p in parts], dtype=np.float32)

            auth_failure_density[i, 0] = float(fail_flags.sum()) / float(step_count)
            fail_idx = np.where(fail_flags > 0)[0]
            if fail_idx.size > 0:
                last_fail = int(fail_idx[-1])
                if np.any(success_flags[last_fail + 1 :] > 0):
                    success_after_fail_chain[i, 0] = 1.0
                if np.any(session_flags[last_fail + 1 :] > 0):
                    session_after_fail_chain[i, 0] = 1.0


        return {
            'auth_failure_ratio': fail,
            'auth_success_ratio': success,
            'privileged_command_ratio': privileged,
            'web_probe_ratio': web_probe,
            'suspicious_keyword_ratio': np.clip(suspicious_ratio, 0.0, 1.0).astype(np.float32),
            'auth_failure_density': np.clip(auth_failure_density, 0.0, 1.0).astype(np.float32),
            'success_after_fail_chain': success_after_fail_chain.astype(np.float32),
            'session_after_fail_chain': session_after_fail_chain.astype(np.float32),
        }

    def _extract_first_user(self, text: str) -> str | None:
        for pattern in self._user_patterns:
            match = pattern.search(text)
            if match:
                value = str(match.group(1) or '').strip().lower()
                if value:
                    return value
        return None

    def _extract_first_uri(self, text: str) -> str | None:
        match = self._http_uri_re.search(text)
        if match:
            value = str(match.group(1) or '').strip().lower()
            if value:
                return value
        for pattern in self._dns_target_patterns:
            match = pattern.search(text)
            if match:
                value = str(match.group(1) or '').strip().lower()
                if value:
                    return value
        return None

    def _extract_first_port(self, text: str) -> str | None:
        match = self._port_re.search(text)
        if not match:
            return None
        value = str(match.group(1) or match.group(2) or '').strip()
        return value or None

    def _extract_event_seconds(self, text: str) -> float | None:
        lowered = str(text or '').strip().lower()
        match = self._syslog_time_re.search(lowered)
        if not match:
            return None
        day = int(match.group(1))
        hh = int(match.group(2))
        mm = int(match.group(3))
        ss = int(match.group(4))
        month_token = lowered[:3]
        month = SYSLOG_MONTHS.get(month_token, 1)
        return float((((month * 31) + day) * 24 + hh) * 3600 + mm * 60 + ss)

    def extract_subject_behavior_features(
        self,
        seq_raw_texts: Iterable[str],
        seq_timestamps: np.ndarray | None = None,
    ) -> Dict[str, np.ndarray]:
        texts = [str(x or "") for x in seq_raw_texts]
        n = len(texts)
        zeros = np.zeros((n, 1), dtype=np.float32)
        if n == 0:
            return {
                'requests_per_ip': zeros,
                'unique_uri_per_ip': zeros,
                'failed_login_per_user': zeros,
                'unique_port_per_ip': zeros,
                'session_length': zeros,
                'mean_interval_per_ip': zeros,
            }

        requests_per_ip = np.zeros((n, 1), dtype=np.float32)
        unique_uri_per_ip = np.zeros((n, 1), dtype=np.float32)
        failed_login_per_user = np.zeros((n, 1), dtype=np.float32)
        unique_port_per_ip = np.zeros((n, 1), dtype=np.float32)
        session_length = np.zeros((n, 1), dtype=np.float32)
        mean_interval_per_ip = np.zeros((n, 1), dtype=np.float32)

        ts_arr = np.asarray(seq_timestamps, dtype=float) if isinstance(seq_timestamps, np.ndarray) else None

        for i, text in enumerate(texts):
            parts = [p.strip() for p in text.split('[SEQ]') if p.strip()]
            step_count = max(len(parts), 1)
            ip_counts: Dict[str, int] = {}
            uri_by_ip: Dict[str, set] = {}
            port_by_ip: Dict[str, set] = {}
            fail_user_counts: Dict[str, int] = {}
            actor_run = 0
            best_run = 0
            last_actor = None
            ip_positions: Dict[str, list] = {}

            tail_ts = None
            if ts_arr is not None and i < len(ts_arr):
                row_ts = np.asarray(ts_arr[i], dtype=float).reshape(-1)
                if row_ts.size >= step_count:
                    tail_ts = row_ts[-step_count:]
            if tail_ts is None:
                parsed_ts = [self._extract_event_seconds(part) for part in parts]
                if all(ts is not None for ts in parsed_ts):
                    tail_ts = np.asarray(parsed_ts, dtype=float)

            for j, part in enumerate(parts):
                lowered = part.lower()
                ips = self._ip_re.findall(lowered)
                ip = ips[0] if ips else None
                user = self._extract_first_user(lowered)
                uri = self._extract_first_uri(lowered)
                port = self._extract_first_port(lowered)

                if ip:
                    ip_counts[ip] = ip_counts.get(ip, 0) + 1
                    ip_positions.setdefault(ip, []).append(j)
                    if uri:
                        uri_by_ip.setdefault(ip, set()).add(uri)
                    if port:
                        port_by_ip.setdefault(ip, set()).add(port)

                if self._auth_fail_re.search(lowered):
                    key = user or '__unknown__'
                    fail_user_counts[key] = fail_user_counts.get(key, 0) + 1

                actor = user or ip
                if actor:
                    if actor == last_actor:
                        actor_run += 1
                    else:
                        actor_run = 1
                        last_actor = actor
                    best_run = max(best_run, actor_run)

            requests_per_ip[i, 0] = float(max(ip_counts.values())) / float(step_count) if ip_counts else 0.0
            unique_uri_per_ip[i, 0] = float(max((len(v) for v in uri_by_ip.values()), default=0)) / float(step_count)
            failed_login_per_user[i, 0] = float(max(fail_user_counts.values())) / float(step_count) if fail_user_counts else 0.0
            unique_port_per_ip[i, 0] = float(max((len(v) for v in port_by_ip.values()), default=0)) / float(step_count)
            session_length[i, 0] = float(best_run) / float(step_count)

            if tail_ts is not None and len(parts) >= 2:
                gaps = []
                for positions in ip_positions.values():
                    if len(positions) < 2:
                        continue
                    pos = np.asarray(positions, dtype=int)
                    ts_vals = tail_ts[pos]
                    diffs = np.diff(ts_vals)
                    diffs = diffs[np.isfinite(diffs)]
                    if diffs.size:
                        gaps.extend(np.abs(diffs).tolist())
                if gaps:
                    mean_interval_per_ip[i, 0] = float(np.log1p(np.mean(gaps)))

        return {
            'requests_per_ip': np.clip(requests_per_ip, 0.0, 1.0).astype(np.float32),
            'unique_uri_per_ip': np.clip(unique_uri_per_ip, 0.0, 1.0).astype(np.float32),
            'failed_login_per_user': np.clip(failed_login_per_user, 0.0, 1.0).astype(np.float32),
            'unique_port_per_ip': np.clip(unique_port_per_ip, 0.0, 1.0).astype(np.float32),
            'session_length': np.clip(session_length, 0.0, 1.0).astype(np.float32),
            'mean_interval_per_ip': mean_interval_per_ip.astype(np.float32),
        }

    def extract_all_features(
        self,
        sequences: np.ndarray,
        seq_timestamps: np.ndarray | None = None,
        seq_texts: Iterable[str] | None = None,
        seq_raw_texts: Iterable[str] | None = None,
    ) -> Dict[str, np.ndarray]:
        self.logger.info('start extracting statistical features...')
        features: Dict[str, np.ndarray] = {}

        need_count = any(
            x in self.feature_names
            for x in [
                'log_frequency', 'entropy', 'normalized_entropy', 'template_count',
                'dominant_ratio', 'repetition_ratio', 'top2_concentration'
            ]
        )
        count_matrix = None
        if need_count:
            count_matrix, _ = self._build_count_matrix(sequences)

        if 'log_frequency' in self.feature_names:
            features['frequency'] = self.extract_frequency_features(sequences, count_matrix=count_matrix)
        if 'entropy' in self.feature_names:
            features['entropy'] = self.extract_entropy_features(sequences, count_matrix=count_matrix)
        if 'normalized_entropy' in self.feature_names:
            features['normalized_entropy'] = self.extract_normalized_entropy_features(sequences, count_matrix=count_matrix)
        if 'template_count' in self.feature_names:
            features['template_count'] = self.extract_template_count_features(sequences, count_matrix=count_matrix)

        if any(x in self.feature_names for x in ['dominant_ratio', 'repetition_ratio', 'top2_concentration']):
            concentration = self.extract_concentration_features(sequences, count_matrix=count_matrix)
            for key in ['dominant_ratio', 'repetition_ratio', 'top2_concentration']:
                if key in self.feature_names:
                    features[key] = concentration[key]

        if 'switch_rate' in self.feature_names:
            features['switch_rate'] = self.extract_switch_rate_features(sequences)
        if 'param_variance' in self.feature_names:
            features['variance'] = self.extract_variance_features(sequences)
        if 'time_interval' in self.feature_names or 'time_burstiness' in self.feature_names:
            time_feat = self.extract_time_interval_features(sequences, seq_timestamps=seq_timestamps)
            if 'time_interval' in self.feature_names:
                features['time_interval'] = time_feat
            if 'time_burstiness' in self.feature_names:
                mean_gap = np.maximum(time_feat[:, [0]], 1e-6)
                features['time_burstiness'] = np.clip(time_feat[:, [1]] / mean_gap, 0.0, 20.0).astype(np.float32)

        if seq_texts is not None and any(
            x in self.feature_names
            for x in [
                'auth_failure_ratio',
                'auth_success_ratio',
                'privileged_command_ratio',
                'web_probe_ratio',
                'suspicious_keyword_ratio',
                'auth_failure_density',
                'success_after_fail_chain',
                'session_after_fail_chain',
            ]
        ):
            text_features = self.extract_security_text_features(seq_texts)
            for key in [
                'auth_failure_ratio',
                'auth_success_ratio',
                'privileged_command_ratio',
                'web_probe_ratio',
                'suspicious_keyword_ratio',
                'auth_failure_density',
                'success_after_fail_chain',
                'session_after_fail_chain',
            ]:
                if key in self.feature_names:
                    features[key] = text_features[key]

        if seq_raw_texts is not None and any(
            x in self.feature_names
            for x in [
                'requests_per_ip',
                'unique_uri_per_ip',
                'failed_login_per_user',
                'unique_port_per_ip',
                'session_length',
                'mean_interval_per_ip',
            ]
        ):
            behavior_features = self.extract_subject_behavior_features(seq_raw_texts, seq_timestamps=seq_timestamps)
            for key in [
                'requests_per_ip',
                'unique_uri_per_ip',
                'failed_login_per_user',
                'unique_port_per_ip',
                'session_length',
                'mean_interval_per_ip',
            ]:
                if key in self.feature_names:
                    features[key] = behavior_features[key]

        all_features = np.hstack([features[k] for k in sorted(features.keys())]) if features else np.zeros((len(np.asarray(sequences)), 0), dtype=np.float32)
        self.logger.info(f'statistical features ready, shape={all_features.shape}')
        return {'combined': all_features, **features}


def main():
    config = Config()
    sequences = np.random.randint(0, 100, size=(1000, 50))
    extractor = StatisticalFeatureExtractor(config)
    features = extractor.extract_all_features(sequences)
    print('statistical feature extraction ok')
    print('input:', sequences.shape)
    print('output:', features['combined'].shape)
    for name, feat in features.items():
        if name != 'combined':
            print(name, feat.shape)


if __name__ == '__main__':
    main()
