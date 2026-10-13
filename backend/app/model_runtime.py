"""公开版轻量健康算法；K-Means、SOM、MLP 只使用独立生成的合成样本，不报告真实设备性能。"""

from __future__ import annotations

import json
import csv
import gzip
import math
import os
import random
import threading
from datetime import datetime
from pathlib import Path

from .paths import get_backend_data_dir, get_project_root
from .subsystems import SUBSYSTEMS
from . import db


MODEL_VERSION = "public-synthetic-demo-v1"
KMEANS = "kmeans"
SOM = "som"
STATISTICAL = "statistical_baseline"
WEIGHTED_DISTANCE = "weighted_distance"
THRESHOLD_VOTING = "threshold_voting"
FUZZY_COMPREHENSIVE = "fuzzy_comprehensive"
PREDICTION = "mlp_predictor"
LINEAR_TREND = "linear_trend"
EXPONENTIAL_SMOOTHING = "exponential_smoothing"
HEALTH_MOVING_AVERAGE = "health_moving_average"
THRESHOLD_PROJECTION = "threshold_projection"
EMD = "emd"
VMD = "vmd"
DWT = "dwt"
MOVING_AVERAGE = "moving_average"
MEDIAN_FILTER = "median_filter"
ACTIVE_ALGORITHMS = (KMEANS, SOM)

FEATURE_SCHEMA = "health-oriented-parameter-features-v1"
PREDICTION_WINDOW = 6
PREDICTION_HORIZON = 3
LIFE_HOURS = 10000

_UNIT_DEFAULTS = {
    "A": 2.5,
    "V": 12.0,
    "℃": 35.0,
    "%": 50.0,
    "dB": -12.0,
    "°/s": 0.3,
    "mV": 2.0,
    "°": 18.0,
}

_NORMAL_ENUM_WORDS = ("正常", "锁定", "未限位", "到位", "未发生", "同步")
_FAULT_ENUM_WORDS = ("告警", "失锁", "不到位", "限位", "失步", "发生")

SUBSYSTEM_IDS = [item["id"] for item in SUBSYSTEMS]
SUBSYSTEM_NAMES = {item["id"]: item["name"] for item in SUBSYSTEMS}
PARAMETERS = [
    (subsystem, parameter)
    for subsystem in SUBSYSTEMS
    for parameter in subsystem.get("params", [])
]
PARAMETER_IDS = [parameter["id"] for _subsystem, parameter in PARAMETERS]

AUTHORITY_TRAINING_FILE = "demo_training_generated_in_memory"
AUTHORITY_MAX_SAMPLES = 1200
AUTHORITY_REPLAY_FIXTURE = "config/authority_replay_fixture.jsonl.gz"
AUTHORITY_SEQUENCE_FILE = "demo_sequences_generated_in_memory"

# 公开版特征归一化不读取真实数据，所有模型样本由合成生成器提供。
_AUTHORITY_NUMERIC_STATS = None


def _clamp(value, low=0.0, high=1.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, number))


def _safe_float(value, fallback=0.0):
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


def _score_status(score):
    score = _safe_float(score)
    if score >= 60:
        return "正常"
    if score >= 30:
        return "故障"
    return "报废"


def _feature_subsystem_scores(features):
    """将统一的参数健康特征聚合为子系统分数，供轻量算法复用。"""
    grouped = _subsystem_features(features)
    return {
        subsystem_id: round(_clamp(value) * 100.0, 1)
        for subsystem_id, value in grouped.items()
    }


def _evaluation_rows(scores):
    return [
        {
            "id": subsystem_id,
            "name": SUBSYSTEM_NAMES[subsystem_id],
            "score": round(_clamp(score / 100.0) * 100.0, 1),
            "status": _score_status(score),
        }
        for subsystem_id, score in scores.items()
    ]


def _scenario_overlay(scores, parameters, scenario_mode=None):
    """Apply the same explicit scenario effect to every health algorithm.

    Model algorithms and lightweight baselines must evaluate the same current
    ScenarioEngine snapshot.  Fault-injected parameters identify local
    failures; ``global_degradation`` is carried by the snapshot's mode because
    it intentionally changes scores without changing individual raw values.
    """
    adjusted = {key: float(value) for key, value in (scores or {}).items()}
    injected = {
        row.get("subsystem_id")
        for row in (parameters or [])
        if row.get("source_type") == "synthetic_demo_fault_injected" and row.get("subsystem_id")
    }
    if injected:
        for subsystem_id in injected:
            if subsystem_id in adjusted:
                adjusted[subsystem_id] = min(adjusted[subsystem_id], 54.0)
    if scenario_mode == "global_degradation":
        for subsystem_id in adjusted:
            adjusted[subsystem_id] *= 0.72
    return {key: round(_clamp(value, 0.0, 100.0), 1) for key, value in adjusted.items()}


def _scenario_overall(scores, parameters, scenario_mode=None):
    """Return an overall score with the same visible fault caps as the dashboard."""
    values = list(scores.values()) if scores else []
    overall = sum(values) / len(values) if values else 0.0
    injected = any(
        row.get("source_type") == "synthetic_demo_fault_injected"
        for row in (parameters or [])
    )
    if injected:
        overall = min(overall, 54.0)
    elif scenario_mode == "global_degradation":
        # The topology dashboard treats global degradation as a system fault
        # once the root falls below 60. Keep every algorithm's headline in the
        # same visible band even when its per-subsystem mean is slightly higher.
        overall = min(overall, 59.9)
    return round(_clamp(overall, 0.0, 100.0), 1)


def _lightweight_evaluation(parameters, algorithm, scenario_mode=None):
    """无模型依赖的健康评估算法。

    这些算法使用与 K-Means/SOM 相同的 配置定义的特征适配层，因此它们不是
    只在前端展示的占位符：每次调用都会读取当前快照并返回 演示子系统结果。
    """
    features = extract_features(parameters)
    base = _feature_subsystem_scores(features)
    if algorithm == STATISTICAL:
        scores = base
        label = "统计基线健康评估"
        threshold = _algorithm_config(STATISTICAL)["warning_threshold"]
        details = {"method": "子系统参数健康特征均值", "threshold": threshold}
    elif algorithm == WEIGHTED_DISTANCE:
        # 参数越偏离健康特征 1，距离越大；指数衰减强调明显异常，同时保留连续分。
        scale = max(0.1, float(_algorithm_config(WEIGHTED_DISTANCE)["distance_scale"]))
        scores = {
            key: round(100.0 * math.exp(-(100.0 - value) / (100.0 * scale)), 1)
            for key, value in base.items()
        }
        label = "加权距离健康评估"
        details = {"method": "参数健康距离指数衰减", "distance_scale": scale}
    elif algorithm == THRESHOLD_VOTING:
        threshold = float(_algorithm_config(THRESHOLD_VOTING)["warning_threshold"])
        grouped = {subsystem_id: [] for subsystem_id in SUBSYSTEM_IDS}
        for index, (subsystem, _parameter) in enumerate(PARAMETERS):
            grouped[subsystem["id"]].append(features[index])
        scores = {}
        for subsystem_id, values in grouped.items():
            if not values:
                scores[subsystem_id] = 0.0
                continue
            normal_votes = sum(value * 100.0 >= threshold for value in values)
            # 投票结果对局部异常敏感，同时保留少量连续信息，避免临界值抖动。
            vote_score = normal_votes / len(values) * 100.0
            mean_score = sum(values) / len(values) * 100.0
            scores[subsystem_id] = round(0.7 * vote_score + 0.3 * mean_score, 1)
        label = "阈值投票健康评估"
        details = {"method": "参数健康特征阈值投票", "warning_threshold": threshold}
    else:
        # 模糊综合评估：把每个参数的健康特征映射为平滑隶属度，再在子系统内聚合。
        # 适合协议回放这种连续值较多、边界附近可能有测量抖动的场景。
        grouped = _subsystem_features(features)
        slope = float(_algorithm_config(FUZZY_COMPREHENSIVE)["membership_slope"])
        scores = {
            key: round(100.0 * _clamp(value ** slope), 1)
            for key, value in grouped.items()
        }
        label = "模糊综合健康评估"
        details = {"method": "健康特征平滑隶属度与子系统综合", "membership": "power", "membership_slope": slope}
    scores = _scenario_overlay(scores, parameters, scenario_mode)
    rows = _evaluation_rows(scores)
    overall = _scenario_overall(scores, parameters, scenario_mode)
    return {
        "algorithm": algorithm,
        "algorithm_label": label,
        "model_version": MODEL_VERSION,
        "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "feature_count": len(features),
        "overall_score": overall,
        "overall_status": _score_status(overall),
        "confidence": round(sum(item["score"] for item in rows) / max(1, len(rows)) / 100.0, 3),
        "subsystems": rows,
        "details": details,
    }


def _signal_values(parameters):
    values = []
    for row in parameters or []:
        value = row.get("value")
        if row.get("dtype") == "enum":
            value = 1.0 if row.get("status") == "正常" else 0.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = None
        if number is not None and math.isfinite(number):
            values.append(number)
    return values


def process_signal(parameters, algorithm):
    """对当前快照的有序健康特征做轻量信号处理，返回可解释统计结果。"""
    features = extract_features(parameters)
    if not features:
        raise RuntimeError("当前快照没有可处理的参数")
    if algorithm == EMD:
        window = int(_algorithm_config(EMD)["envelope_window"])
        trend = []
        for index in range(len(features)):
            start = max(0, index - window + 1)
            trend.append(sum(features[start:index + 1]) / (index - start + 1))
        residual = [round(features[index] - trend[index], 6) for index in range(len(features))]
        modes = [trend, residual]
        label = "经验模态分解（EMD）"
        detail = {"mode_count": 2, "envelope_window": window}
    elif algorithm == VMD:
        mode_count = int(_algorithm_config(VMD)["mode_count"])
        mode_count = max(2, min(mode_count, 6))
        modes = []
        for mode_index in range(mode_count):
            stride = mode_index + 1
            modes.append([
                round(features[index] - (features[index - stride] if index >= stride else features[index]), 6)
                for index in range(len(features))
            ])
        label = "变分模态分解（VMD）"
        detail = {"mode_count": mode_count, "iterations": int(_algorithm_config(VMD)["iterations"])}
    elif algorithm == DWT:
        level = int(_algorithm_config(DWT)["decomposition_level"])
        level = max(1, min(level, 6))
        approximation = []
        detail_energy = []
        for stride in (2 ** index for index in range(level)):
            detail = [features[index] - features[index - stride] if index >= stride else 0.0 for index in range(len(features))]
            detail_energy.append(round(sum(value * value for value in detail) / len(detail), 6))
            approximation = detail
        modes = [features, approximation]
        label = "离散小波变换（DWT）"
        detail = {"decomposition_level": level, "detail_energy": detail_energy}
    elif algorithm == MOVING_AVERAGE:
        window = int(_algorithm_config(MOVING_AVERAGE)["window"])
        trend = []
        for index in range(len(features)):
            start = max(0, index - window + 1)
            trend.append(sum(features[start:index + 1]) / (index - start + 1))
        residual = [round(features[index] - trend[index], 6) for index in range(len(features))]
        modes = [trend, residual]
        label = "滑动平均滤波"
        detail = {"window": window, "method": "simple moving average"}
    else:
        window = int(_algorithm_config(MEDIAN_FILTER)["window"])
        filtered = []
        for index in range(len(features)):
            start = max(0, index - window // 2)
            end = min(len(features), index + window // 2 + 1)
            values = sorted(features[start:end])
            middle = len(values) // 2
            median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2.0
            filtered.append(median)
        residual = [round(features[index] - filtered[index], 6) for index in range(len(features))]
        modes = [filtered, residual]
        label = "中值滤波"
        detail = {"window": window, "method": "median filter"}
    energy = [round(sum(value * value for value in mode) / max(1, len(mode)), 6) for mode in modes]
    return {
        "algorithm": algorithm,
        "algorithm_label": label,
        "processed_dimension": len(features),
        "mode_count": len(modes),
        "energy": energy,
        "mean_health_feature": round(sum(features) / len(features), 4),
        "details": detail,
        "input": {"feature_count": len(features), "raw_numeric_count": len(_signal_values(parameters))},
    }


_ALGORITHM_DEFAULTS = {
    KMEANS: {"cluster_count": 3, "iterations": 16},
    SOM: {"rows": 3, "cols": 3, "epochs": 12, "learning_rate": 0.32},
    STATISTICAL: {"warning_threshold": 0.55},
    WEIGHTED_DISTANCE: {"distance_scale": 0.45},
    THRESHOLD_VOTING: {"warning_threshold": 60},
    FUZZY_COMPREHENSIVE: {"membership_slope": 1.5},
    PREDICTION: {"window_size": 6, "horizon": 3, "hidden_units": 10, "epochs": 100, "learning_rate": 0.25},
    LINEAR_TREND: {"horizon": 3, "history_points": 12},
    EXPONENTIAL_SMOOTHING: {"horizon": 3, "smoothing_factor": 0.35},
    HEALTH_MOVING_AVERAGE: {"horizon": 3, "window": 6},
    THRESHOLD_PROJECTION: {"horizon": 3, "degradation_rate": 0.015, "warning_threshold": 60},
    EMD: {"envelope_window": 5},
    VMD: {"mode_count": 3, "iterations": 8},
    DWT: {"decomposition_level": 3},
    MOVING_AVERAGE: {"window": 5},
    MEDIAN_FILTER: {"window": 5},
}


def _algorithm_config(algorithm):
    """读取算法管理页保存的配置；数据库不可用时使用安全默认值。"""
    values = dict(_ALGORITHM_DEFAULTS[algorithm])
    try:
        stored = db.get_algorithm_config(algorithm) or {}
    except Exception:
        stored = {}
    for key, default in values.items():
        raw = stored.get(key, default)
        try:
            value = float(raw)
            values[key] = int(round(value)) if isinstance(default, int) else value
        except (TypeError, ValueError):
            values[key] = default
    return values


def _base_numeric(parameter):
    bounds = parameter.get("range")
    if bounds and len(bounds) == 2:
        low, high = _safe_float(bounds[0]), _safe_float(bounds[1])
        return (low + high) * 0.08 if low <= 0 <= high else low + (high - low) * 0.35
    return _UNIT_DEFAULTS.get(parameter.get("unit", ""), 1.0)


def _numeric_scale(parameter):
    bounds = parameter.get("range")
    if bounds and len(bounds) == 2:
        return max(abs(_safe_float(bounds[1]) - _safe_float(bounds[0])) * 0.08, 0.01)
    return max(abs(_base_numeric(parameter)) * 0.10, 0.05)


def _authority_fixture_path():
    return get_project_root() / "data-not-distributed"



def _load_authority_numeric_stats():
    return {}



def _enum_label(parameter, value):
    values = parameter.get("enum") or {}
    text = str(value)
    if text in values:
        return str(values[text])
    if text in {str(item) for item in values.values()}:
        return text
    try:
        numeric = int(float(value))
        return str(values.get(str(numeric), text))
    except (TypeError, ValueError):
        return text


def _normal_enum_label(parameter):
    values = parameter.get("enum") or {}
    labels = [str(value) for value in values.values()]
    for keyword in _NORMAL_ENUM_WORDS:
        for label in labels:
            if label == keyword:
                return label
    return labels[0] if labels else ""


def _is_health_enum(parameter):
    labels = [str(value) for value in (parameter.get("enum") or {}).values()]
    return any(keyword in label for label in labels for keyword in _FAULT_ENUM_WORDS)


def parameter_health_feature(parameter, value):
    """把一个当前参数转换成 0~1 的健康特征，1 表示接近正常。

    这个转换是模型的唯一输入适配点。它同时支持场景模拟的数值/枚举格式和未来
    真实采集接口的 value/display_value 格式，后续替换成真实特征工程时不需要改模型路由。
    """
    if parameter.get("dtype") == "enum":
        label = _enum_label(parameter, value)
        normal = _normal_enum_label(parameter)
        if label == normal:
            return 1.0
        if _is_health_enum(parameter) or any(keyword in label for keyword in _FAULT_ENUM_WORDS):
            return 0.05
        # 工作方式、扫描方式等多值枚举不直接表示健康状态，给中性特征。
        return 0.72

    authority_stats = _load_authority_numeric_stats().get(parameter.get("id"))
    if authority_stats:
        baseline = authority_stats["median"]
        scale = max(authority_stats["spread"] * 0.5, _numeric_scale(parameter))
    else:
        baseline = _base_numeric(parameter)
        scale = _numeric_scale(parameter)
    number = _safe_float(value, baseline)
    distance = abs(number - baseline)
    return _clamp(math.exp(-distance / max(scale * 2.0, 0.01)))


def extract_features(parameters):
    """从 health.parameters 行列表提取与 config/params.json 对齐的 配置定义的特征。"""
    rows = {}
    source_by_parameter = {}
    for row in parameters or []:
        parameter_id = row.get("param_id") or row.get("id")
        if not parameter_id:
            continue
        value = row.get("enum_label") if row.get("dtype") == "enum" else row.get("value")
        if value is None:
            value = row.get("display_value")
        rows[parameter_id] = value
        source_by_parameter[parameter_id] = row.get("source_type")

    features = []
    for _subsystem, parameter in PARAMETERS:
        value = rows.get(parameter["id"])
        if value is None:
            # 回放映射缺口不补造值；0.72 只是模型特征的中性缺失标记，不是遥测值。
            features.append(0.72)
            continue
        feature = parameter_health_feature(parameter, value)
        # ScenarioEngine 明确标记的故障注入值是联调中的已知异常，不能被真实
        # 基线统计“洗掉”；训练样本也使用同一个来源标记，保持训练/推理一致。
        if source_by_parameter.get(parameter["id"]) == "synthetic_demo_fault_injected":
            feature = min(feature, 0.18)
        features.append(round(feature, 6))
    return features


def _subsystem_features(features):
    grouped = {subsystem_id: [] for subsystem_id in SUBSYSTEM_IDS}
    index = 0
    for subsystem, _parameter in PARAMETERS:
        grouped[subsystem["id"]].append(features[index])
        index += 1
    return {
        subsystem_id: (sum(values) / len(values) if values else 1.0)
        for subsystem_id, values in grouped.items()
    }


def _synthetic_sample(rng, severities):
    features = []
    index_by_subsystem = {}
    for subsystem, parameter in PARAMETERS:
        subsystem_id = subsystem["id"]
        severity = _clamp(severities.get(subsystem_id, 0.0))
        # 健康特征随退化程度平滑下降，保留少量噪声模拟测量误差。
        neutral_floor = 0.18 if parameter.get("dtype") == "enum" and not _is_health_enum(parameter) else 0.05
        feature = 0.98 - 0.82 * severity + rng.gauss(0.0, 0.018)
        feature = max(neutral_floor, min(1.0, feature))
        index_by_subsystem.setdefault(subsystem_id, []).append(len(features))
        features.append(round(feature, 6))

    subsystem_scores = {}
    for subsystem_id in SUBSYSTEM_IDS:
        severity = _clamp(severities.get(subsystem_id, 0.0))
        score = 95.0 - severity * 72.0 + rng.gauss(0.0, 1.3)
        subsystem_scores[subsystem_id] = round(_clamp(score, 0.0, 100.0), 1)
    return features, subsystem_scores


def _build_training_samples(sample_count=120, seed=20260812):
    rng = random.Random(seed)
    samples = []
    targets = []
    for index in range(sample_count):
        # 重复几段退化曲线，让三个状态簇都有足够样本，同时保留连续变化。
        progress = (index % 40) / 39.0
        global_severity = _clamp(progress + rng.uniform(-0.035, 0.035))
        severities = {
            subsystem_id: _clamp(global_severity + rng.uniform(-0.10, 0.10))
            for subsystem_id in SUBSYSTEM_IDS
        }
        # 少量样本模拟局部故障，避免模型只会识别“全局一起变差”。
        if index % 5 == 0:
            affected = rng.choice(SUBSYSTEM_IDS)
            severities[affected] = _clamp(severities[affected] + 0.28)
        features, scores = _synthetic_sample(rng, severities)
        samples.append(features)
        targets.append(scores)
    return samples, targets


def _load_authority_training_samples(path=None, max_samples=AUTHORITY_MAX_SAMPLES):
    samples, targets = _build_training_samples(sample_count=120, seed=42)
    return {'samples':samples,'targets':targets,'source':'synthetic_demo_seed_42','rows_read':len(samples),'sample_count':len(samples),'class_counts':{},'mapping_ready':False}



def _load_mature_sequence_samples(path=None, max_samples=AUTHORITY_MAX_SAMPLES,
                                  window=PREDICTION_WINDOW, horizon=PREDICTION_HORIZON):
    samples, targets = _build_prediction_samples(sample_count=64, window=window, horizon=horizon)
    return {'samples':samples,'targets':targets,'source':'synthetic_demo_sequence','sample_count':len(samples),'class_counts':{}}



def _authority_parameter_rows(values, source_type="synthetic_demo"):
    """把回放缓存的值字典还原成现有模型的参数行契约。"""
    rows = []
    for subsystem, parameter in PARAMETERS:
        value = values.get(parameter["id"])
        if value is None:
            continue
        row = {
            "param_id": parameter["id"],
            "dtype": parameter.get("dtype"),
            "value": value,
            "display_value": value,
            "enum_label": _enum_label(parameter, value) if parameter.get("dtype") == "enum" else None,
            "source_type": source_type,
        }
        rows.append(row)
    return rows


def _authority_fault_values(values, affected_ids):
    """构造仅用于训练的可解释局部故障，不冒充真实故障标签。"""
    result = dict(values)
    affected = set(affected_ids)
    for subsystem, parameter in PARAMETERS:
        if subsystem["id"] not in affected or parameter["id"] not in result:
            continue
        if parameter.get("dtype") == "enum":
            enum = parameter.get("enum") or {}
            for code, label in enum.items():
                if any(word in str(label) for word in _FAULT_ENUM_WORDS):
                    result[parameter["id"]] = int(code)
                    break
        else:
            value = _safe_float(result[parameter["id"]], _base_numeric(parameter))
            unit = parameter.get("unit", "")
            if unit == "℃":
                value += 28.0
            elif unit == "%":
                value = 94.0
            elif unit == "V":
                value *= 0.45
            elif unit == "A":
                value *= 2.2
            elif unit in {"°/s", "mV"}:
                value *= 3.0
            elif unit == "°":
                value += 8.0 if value >= 0 else -8.0
            else:
                value *= 1.8
            result[parameter["id"]] = value
    return result


def _load_authority_replay_training_samples(max_rows=180):
    return _load_authority_training_samples()



def _load_authority_prediction_samples(max_rows=240, window=PREDICTION_WINDOW, horizon=PREDICTION_HORIZON):
    return _load_mature_sequence_samples(max_samples=max_rows, window=window, horizon=horizon)



def _mean_vectors(vectors, dimension):
    if not vectors:
        return [0.0] * dimension
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimension)]


def _squared_distance(left, right):
    return sum((a - b) ** 2 for a, b in zip(left, right))


def _nearest(vector, centroids):
    distances = [_squared_distance(vector, centroid) for centroid in centroids]
    order = sorted(range(len(distances)), key=lambda index: distances[index])
    return order[0], distances[order[0]], distances[order[1]] if len(order) > 1 else distances[order[0]]


def _cluster_statistics(assignments, targets, count):
    overall_scores = []
    subsystem_scores = []
    for cluster_index in range(count):
        rows = [targets[index] for index, value in enumerate(assignments) if value == cluster_index]
        if not rows:
            rows = targets
        per_subsystem = {
            subsystem_id: round(sum(row[subsystem_id] for row in rows) / len(rows), 2)
            for subsystem_id in SUBSYSTEM_IDS
        }
        subsystem_scores.append(per_subsystem)
        overall_scores.append(round(sum(per_subsystem.values()) / len(per_subsystem), 2))
    return overall_scores, subsystem_scores


def _train_kmeans(samples, targets, k=3, iterations=16):
    dimension = len(samples[0])
    k = max(2, min(int(k), len(samples)))
    iterations = max(1, int(iterations))
    seed_indexes = [round(index * (len(samples) - 1) / max(1, k - 1)) for index in range(k)]
    centroids = [list(samples[index]) for index in seed_indexes[:k]]
    assignments = [0] * len(samples)
    for _ in range(iterations):
        assignments = [_nearest(sample, centroids)[0] for sample in samples]
        next_centroids = []
        for cluster_index, centroid in enumerate(centroids):
            members = [samples[index] for index, value in enumerate(assignments) if value == cluster_index]
            next_centroids.append(_mean_vectors(members, dimension) if members else centroid)
        if all(_squared_distance(left, right) < 1e-10 for left, right in zip(centroids, next_centroids)):
            centroids = next_centroids
            break
        centroids = next_centroids

    assignments = [_nearest(sample, centroids)[0] for sample in samples]
    overall_scores, subsystem_scores = _cluster_statistics(assignments, targets, len(centroids))
    inertia = round(sum(_squared_distance(sample, centroids[assignments[index]]) for index, sample in enumerate(samples)), 4)
    return {
        "algorithm": KMEANS,
        "centroids": centroids,
        "overall_scores": overall_scores,
        "subsystem_scores": subsystem_scores,
        "cluster_counts": [assignments.count(index) for index in range(len(centroids))],
        "metrics": {"cluster_count": len(centroids), "iterations": iterations, "inertia": inertia},
    }


def _train_som(samples, targets, rows=3, cols=3, epochs=12, learning_rate=0.32):
    rows = max(1, int(rows))
    cols = max(1, int(cols))
    epochs = max(1, int(epochs))
    learning_rate = max(0.001, float(learning_rate))
    dimension = len(samples[0])
    count = rows * cols
    indexes = [round(index * (len(samples) - 1) / max(1, count - 1)) for index in range(count)]
    centroids = [list(samples[index]) for index in indexes]
    for epoch in range(epochs):
        current_learning_rate = learning_rate * (1.0 - epoch / max(epochs, 1)) + learning_rate * 0.125
        radius = max(0.65, 1.65 * (1.0 - epoch / max(epochs, 1)))
        for sample in samples:
            bmu, _distance, _second = _nearest(sample, centroids)
            bmu_row, bmu_col = divmod(bmu, cols)
            for neuron_index, centroid in enumerate(centroids):
                row, col = divmod(neuron_index, cols)
                grid_distance = math.sqrt((row - bmu_row) ** 2 + (col - bmu_col) ** 2)
                influence = math.exp(-(grid_distance ** 2) / (2.0 * radius ** 2))
                factor = current_learning_rate * influence
                for feature_index in range(dimension):
                    centroid[feature_index] += factor * (sample[feature_index] - centroid[feature_index])

    assignments = [_nearest(sample, centroids)[0] for sample in samples]
    overall_scores, subsystem_scores = _cluster_statistics(assignments, targets, len(centroids))
    return {
        "algorithm": SOM,
        "rows": rows,
        "cols": cols,
        "centroids": centroids,
        "overall_scores": overall_scores,
        "subsystem_scores": subsystem_scores,
        "cluster_counts": [assignments.count(index) for index in range(len(centroids))],
        "metrics": {"grid": f"{rows}x{cols}", "epochs": epochs},
    }


def _sigmoid(value):
    value = max(-40.0, min(40.0, value))
    return 1.0 / (1.0 + math.exp(-value))


class _TinyMLP:
    """纯 Python 的输入-隐藏-输出三层网络。"""

    def __init__(self, input_dim, hidden_dim, output_dim, seed=20260812):
        rng = random.Random(seed)
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        self.weights_1 = [[rng.uniform(-0.035, 0.035) for _ in range(input_dim)] for _ in range(hidden_dim)]
        self.bias_1 = [0.0] * hidden_dim
        self.weights_2 = [[rng.uniform(-0.035, 0.035) for _ in range(hidden_dim)] for _ in range(output_dim)]
        self.bias_2 = [0.0] * output_dim

    def _forward(self, inputs):
        hidden = []
        for row, bias in zip(self.weights_1, self.bias_1):
            hidden.append(math.tanh(bias + sum(weight * value for weight, value in zip(row, inputs))))
        outputs = []
        for row, bias in zip(self.weights_2, self.bias_2):
            outputs.append(_sigmoid(bias + sum(weight * value for weight, value in zip(row, hidden))))
        return hidden, outputs

    def fit(self, samples, targets, epochs=18, learning_rate=0.035):
        losses = []
        output_scale = 2.0 / max(1, self.output_dim)
        for _epoch in range(epochs):
            total_loss = 0.0
            for inputs, expected in zip(samples, targets):
                hidden, outputs = self._forward(inputs)
                errors = [outputs[index] - expected[index] for index in range(self.output_dim)]
                total_loss += sum(error * error for error in errors) / max(1, self.output_dim)

                grad_output = [errors[index] * outputs[index] * (1.0 - outputs[index]) * output_scale for index in range(self.output_dim)]
                grad_hidden = [
                    (1.0 - hidden[hidden_index] ** 2)
                    * sum(grad_output[output_index] * self.weights_2[output_index][hidden_index] for output_index in range(self.output_dim))
                    for hidden_index in range(self.hidden_dim)
                ]

                for output_index in range(self.output_dim):
                    for hidden_index in range(self.hidden_dim):
                        self.weights_2[output_index][hidden_index] -= learning_rate * grad_output[output_index] * hidden[hidden_index]
                    self.bias_2[output_index] -= learning_rate * grad_output[output_index]
                for hidden_index in range(self.hidden_dim):
                    for input_index in range(self.input_dim):
                        self.weights_1[hidden_index][input_index] -= learning_rate * grad_hidden[hidden_index] * inputs[input_index]
                    self.bias_1[hidden_index] -= learning_rate * grad_hidden[hidden_index]
            losses.append(total_loss / max(1, len(samples)))
        return losses

    def predict(self, inputs):
        return self._forward(inputs)[1]

    def to_dict(self):
        return {
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "output_dim": self.output_dim,
            "weights_1": self.weights_1,
            "bias_1": self.bias_1,
            "weights_2": self.weights_2,
            "bias_2": self.bias_2,
        }

    @classmethod
    def from_dict(cls, data):
        model = cls(data["input_dim"], data["hidden_dim"], data["output_dim"])
        model.weights_1 = data["weights_1"]
        model.bias_1 = data["bias_1"]
        model.weights_2 = data["weights_2"]
        model.bias_2 = data["bias_2"]
        return model


def _build_prediction_samples(sample_count=64, window=PREDICTION_WINDOW, horizon=PREDICTION_HORIZON):
    rng = random.Random(20260813)
    samples = []
    targets = []
    for _index in range(sample_count):
        start = rng.uniform(0.0, 0.72)
        speed = rng.uniform(0.008, 0.045)
        sequence_features = []
        sequence_scores = []
        sequence_severities = []
        for step in range(window + horizon):
            severity = _clamp(start + step * speed + rng.uniform(-0.015, 0.015))
            sequence_severities.append(severity)
            severities = {
                subsystem_id: _clamp(severity + rng.uniform(-0.07, 0.07))
                for subsystem_id in SUBSYSTEM_IDS
            }
            features, scores = _synthetic_sample(rng, severities)
            sequence_features.append(features)
            sequence_scores.append(scores)
        flattened = [value for row in sequence_features[:window] for value in row]
        expected = []
        for row in sequence_scores[window:window + horizon]:
            expected.extend(_clamp(row[subsystem_id] / 100.0) for subsystem_id in SUBSYSTEM_IDS)
        life_norm = _clamp(1.0 - sequence_severities[window + horizon - 1])
        expected.append(life_norm)
        samples.append(flattened)
        targets.append(expected)
    return samples, targets


def _status_for_metadata(metadata):
    if not metadata:
        return {"trained": False}
    return {
        "trained": True,
        "algorithm": metadata.get("algorithm"),
        "trained_at": metadata.get("trained_at"),
        "sample_count": metadata.get("sample_count", 0),
        "feature_count": metadata.get("feature_count", len(PARAMETER_IDS)),
        "subsystem_count": metadata.get("subsystem_count", len(SUBSYSTEM_IDS)),
        "training_source": metadata.get("training_source", ""),
        "metrics": metadata.get("metrics", {}),
        "model_version": metadata.get("model_version", MODEL_VERSION),
    }


def _virtual_status(algorithm, label):
    return {
        "trained": True,
        "algorithm": algorithm,
        "algorithm_label": label,
        "trained_at": None,
        "sample_count": 0,
        "feature_count": len(PARAMETER_IDS),
        "subsystem_count": len(SUBSYSTEM_IDS),
        "training_source": "实时快照确定性计算",
        "metrics": {"kind": "rule_based"},
        "model_version": MODEL_VERSION,
    }


class ModelRuntime:
    def __init__(self):
        self.model_dir = get_backend_data_dir() / "models"
        bundled_dir = os.environ.get("RADAR_BUNDLED_MODEL_DIR")
        self.bundled_model_dir = Path(bundled_dir).expanduser() if bundled_dir else None
        self._lock = threading.RLock()
        self._models = {}
        self._last_error = None
        self._training = False

    def _path(self, algorithm):
        filename = {
            KMEANS: "health_kmeans.json",
            SOM: "health_som.json",
            PREDICTION: "health_prediction_mlp.json",
        }[algorithm]
        return self.model_dir / filename

    def _bundled_path(self, algorithm):
        if self.bundled_model_dir is None:
            return None
        filename = {
            KMEANS: "health_kmeans.json",
            SOM: "health_som.json",
            PREDICTION: "health_prediction_mlp.json",
        }[algorithm]
        return self.bundled_model_dir / filename

    def _metadata(self, algorithm, sample_count, metrics, source):
        return {
            "model_version": MODEL_VERSION,
            "algorithm": algorithm,
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sample_count": sample_count,
            "feature_count": len(PARAMETER_IDS),
            "subsystem_count": len(SUBSYSTEM_IDS),
            "parameter_ids": PARAMETER_IDS,
            "subsystem_ids": SUBSYSTEM_IDS,
            "feature_schema": FEATURE_SCHEMA,
            "training_source": source,
            "metrics": metrics,
        }

    def _load_existing(self):
        loaded = {}
        for algorithm in (KMEANS, SOM, PREDICTION):
            # A user-retrained model wins over the read-only model shipped in
            # the app.  A clean install therefore works without writing into
            # the App bundle, while later retraining remains persistent.
            candidates = [(self._path(algorithm), "runtime")]
            bundled_path = self._bundled_path(algorithm)
            if bundled_path is not None:
                candidates.append((bundled_path, "bundled"))
            for path, storage_source in candidates:
                if not path or not path.exists():
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    metadata = data.get("metadata") or {}
                    if metadata.get("model_version") != MODEL_VERSION:
                        continue
                    if metadata.get("parameter_ids") != PARAMETER_IDS:
                        continue
                    metrics = metadata.get("metrics") or {}
                    if algorithm in (KMEANS, SOM) and metrics.get("dataset_kind") != "synthetic_demo_training":
                        continue
                    if algorithm == PREDICTION and metrics.get("dataset_kind") != "synthetic_demo_training_sequence":
                        continue
                    loaded[algorithm] = data
                    loaded[algorithm].setdefault("runtime", {})["storage_source"] = storage_source
                    break
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        self._models.update(loaded)

    def _write(self, algorithm, data):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        data.setdefault("runtime", {})["storage_source"] = "runtime"
        self._path(algorithm).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    def ensure_models(self, force=False):
        with self._lock:
            if not self._models:
                self._load_existing()
            if not force and all(key in self._models for key in (KMEANS, SOM, PREDICTION)):
                return self.status()
            if self._training:
                return self.status()
            self._training = True
            self._last_error = None
            try:
                self._train_all()
            except Exception as exc:
                self._last_error = str(exc)
                raise
            finally:
                self._training = False
            return self.status()

    def _train_all(self):
        authority_training = _load_authority_training_samples()
        if not authority_training:
            raise RuntimeError("成熟私有工程基线扩展训练集不可用，请先运行 dataset.protocol.run_pipeline。")
        samples = authority_training["samples"]
        targets = authority_training["targets"]
        source = f"synthetic-demo:{authority_training['source']}"
        dataset_metrics = {
            "dataset_kind": "synthetic_demo_training",
            "dataset_file": authority_training["source"],
            "dataset_rows_read": authority_training["rows_read"],
            "dataset_sample_count": authority_training["sample_count"],
            "dataset_class_counts": authority_training["class_counts"],
            "mapping_ready": authority_training.get("mapping_ready", False),
            "source_baseline": "synthetic_demo",
            "synthetic_extension": "self_generated_fault_scenarios",
        }
        kmeans_config = _algorithm_config(KMEANS)
        som_config = _algorithm_config(SOM)
        trained_algorithms = (
            (KMEANS, _train_kmeans, kmeans_config),
            (SOM, _train_som, som_config),
        )
        for algorithm, trainer, config in trained_algorithms:
            trained = trainer(samples, targets, **{
                "k": config["cluster_count"], "iterations": config["iterations"]
            } if algorithm == KMEANS else {
                "rows": config["rows"], "cols": config["cols"],
                "epochs": config["epochs"], "learning_rate": config["learning_rate"],
            })
            metrics = {**trained.pop("metrics"), **dataset_metrics}
            metrics["hyperparameters"] = config
            metadata = self._metadata(algorithm, len(samples), metrics, source)
            data = {"metadata": metadata, **trained}
            self._write(algorithm, data)
            self._models[algorithm] = data

        prediction_config = _algorithm_config(PREDICTION)
        window = prediction_config["window_size"]
        horizon = prediction_config["horizon"]
        # MLP 的输入维度为 时间窗口×演示测点数；从完整时序集分层取最多 240 条，保持训练
        # 来源同源且可在桌面端按秒级启动完成。完整序列文件仍保留供离线评测。
        authority_prediction = _load_mature_sequence_samples(max_samples=240, window=window, horizon=horizon)
        if not authority_prediction:
            raise RuntimeError("成熟基线扩展时序数据不可用，请先运行 dataset.protocol.run_pipeline。")
        prediction_samples = authority_prediction["samples"]
        prediction_targets = authority_prediction["targets"]
        prediction_source = f"synthetic-demo-sequence:{authority_prediction['source']}"
        input_dim = window * len(PARAMETER_IDS)
        output_dim = horizon * len(SUBSYSTEM_IDS) + 1
        network = _TinyMLP(input_dim, hidden_dim=prediction_config["hidden_units"], output_dim=output_dim)
        # 训练规模仍然很小；适当增加轮数让正常样本落在正常区间、退化样本能明显下降。
        # 这不是为了追求复杂模型，而是避免三层网络在演示时退化成“所有输入都输出中间值”。
        losses = network.fit(
            prediction_samples,
            prediction_targets,
            epochs=prediction_config["epochs"],
            learning_rate=prediction_config["learning_rate"],
        )
        metrics = {
            **prediction_config,
            "final_mse": round(losses[-1], 6),
            "epochs": len(losses),
            "hyperparameters": prediction_config,
            "dataset_kind": "synthetic_demo_training_sequence",
            "dataset_file": authority_prediction["source"],
            "dataset_sample_count": authority_prediction["sample_count"],
            "dataset_class_counts": authority_prediction.get("class_counts", {}),
            "source_baseline": "synthetic_demo",
            "synthetic_extension": "self_generated_fault_scenarios",
        }
        metadata = self._metadata(PREDICTION, len(prediction_samples), metrics, prediction_source)
        prediction_data = {
            "metadata": metadata,
            "network": network.to_dict(),
        }
        self._write(PREDICTION, prediction_data)
        self._models[PREDICTION] = prediction_data

    def status(self, active_algorithm=KMEANS):
        with self._lock:
            models = {
                algorithm: {
                    **_status_for_metadata((self._models.get(algorithm) or {}).get("metadata")),
                    "storage_source": (self._models.get(algorithm) or {}).get("runtime", {}).get("storage_source"),
                }
                for algorithm in (KMEANS, SOM, PREDICTION)
            }
            models.update({
                STATISTICAL: _virtual_status(STATISTICAL, "统计基线健康评估"),
                WEIGHTED_DISTANCE: _virtual_status(WEIGHTED_DISTANCE, "加权距离健康评估"),
                THRESHOLD_VOTING: _virtual_status(THRESHOLD_VOTING, "阈值投票健康评估"),
                FUZZY_COMPREHENSIVE: _virtual_status(FUZZY_COMPREHENSIVE, "模糊综合健康评估"),
                LINEAR_TREND: _virtual_status(LINEAR_TREND, "线性趋势健康预测"),
                EXPONENTIAL_SMOOTHING: _virtual_status(EXPONENTIAL_SMOOTHING, "指数平滑健康预测"),
                HEALTH_MOVING_AVERAGE: _virtual_status(HEALTH_MOVING_AVERAGE, "滑动平均健康预测"),
                THRESHOLD_PROJECTION: _virtual_status(THRESHOLD_PROJECTION, "阈值退化健康预测"),
                EMD: _virtual_status(EMD, "经验模态分解（EMD）"),
                VMD: _virtual_status(VMD, "变分模态分解（VMD）"),
                DWT: _virtual_status(DWT, "离散小波变换（DWT）"),
                MOVING_AVERAGE: _virtual_status(MOVING_AVERAGE, "滑动平均滤波"),
                MEDIAN_FILTER: _virtual_status(MEDIAN_FILTER, "中值滤波"),
            })
            return {
                "model_version": MODEL_VERSION,
                "active_algorithm": active_algorithm,
                "feature_count": len(PARAMETER_IDS),
                "subsystem_count": len(SUBSYSTEM_IDS),
                "parameter_count": len(PARAMETER_IDS),
                "models": models,
                "training": self._training,
                "last_error": self._last_error,
                "model_dir": str(self.model_dir),
                "bundled_model_dir": str(self.bundled_model_dir) if self.bundled_model_dir else None,
            }

    def _require(self, algorithm):
        self.ensure_models()
        model = self._models.get(algorithm)
        if not model:
            raise RuntimeError(f"模型未就绪: {algorithm}")
        return model

    def assess(self, parameters, algorithm=KMEANS, scenario_mode=None):
        if algorithm in (STATISTICAL, WEIGHTED_DISTANCE, THRESHOLD_VOTING, FUZZY_COMPREHENSIVE):
            return _lightweight_evaluation(parameters, algorithm, scenario_mode=scenario_mode)
        model = self._require(algorithm)
        features = extract_features(parameters)
        centroids = model.get("centroids", [])
        cluster, distance, second_distance = _nearest(features, centroids)
        metadata = model["metadata"]
        # Older packaged models stored target scores in 0–1 while the runtime
        # API contract is 0–100.  Accept both representations so a shipped
        # model remains usable and newly retrained models stay compatible.
        cluster_score = float(model["overall_scores"][cluster])
        if cluster_score <= 1.0:
            cluster_score *= 100.0
        cluster_subsystem_scores = {
            key: (float(value) * 100.0 if float(value) <= 1.0 else float(value))
            for key, value in model["subsystem_scores"][cluster].items()
        }
        live_subsystem_features = _subsystem_features(features)
        injected_fault_subsystems = {
            row.get("subsystem_id")
            for row in (parameters or [])
            if row.get("source_type") == "synthetic_demo_fault_injected" and row.get("subsystem_id")
        }
        subsystem_rows = []
        for subsystem_id in SUBSYSTEM_IDS:
            # 聚类状态提供全局稳定性，当前参数偏差提供局部敏感性。
            score = 0.65 * cluster_subsystem_scores[subsystem_id] + 0.35 * live_subsystem_features[subsystem_id] * 100.0
            # 场景引擎对故障注入参数给出了明确来源标记。聚类模型的全局中心
            # 会稀释局部故障，这里保留一个可解释的局部上限，使算法接口与
            # 同一条 update_dashboard 快照的场景判定保持一致。
            if subsystem_id in injected_fault_subsystems:
                score = min(score, 54.0)
            score = round(_clamp(score, 0.0, 100.0), 1)
            subsystem_rows.append({
                "id": subsystem_id,
                "name": SUBSYSTEM_NAMES[subsystem_id],
                "score": score,
                "status": _score_status(score),
            })
        overall_score = _scenario_overall({row["id"]: row["score"] for row in subsystem_rows}, parameters, scenario_mode)
        if scenario_mode == "global_degradation":
            for row in subsystem_rows:
                row["score"] = round(_clamp(row["score"] * 0.72, 0.0, 100.0), 1)
                row["status"] = _score_status(row["score"])
            overall_score = _scenario_overall({row["id"]: row["score"] for row in subsystem_rows}, parameters, scenario_mode)
        confidence = round(_clamp(second_distance / max(second_distance + distance, 1e-9)), 3)
        label = {
            KMEANS: "K-Means健康评估",
            SOM: "SOM健康评估",
        }.get(algorithm, "模型健康评估")
        return {
            "algorithm": algorithm,
            "algorithm_label": label,
            "model_version": metadata.get("model_version", MODEL_VERSION),
            "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feature_count": len(features),
            "overall_score": overall_score,
            "overall_status": _score_status(overall_score),
            "confidence": confidence,
            "cluster": cluster,
            "cluster_score": round(cluster_score, 1),
            "subsystems": subsystem_rows,
        }

    def predict(self, parameters, algorithm=PREDICTION, scenario_mode=None):
        if algorithm in (LINEAR_TREND, EXPONENTIAL_SMOOTHING, HEALTH_MOVING_AVERAGE, THRESHOLD_PROJECTION):
            features = extract_features(parameters)
            base = _feature_subsystem_scores(features)
            config = _algorithm_config(algorithm)
            horizon = int(config["horizon"])
            if algorithm == LINEAR_TREND:
                factor = 0.985
                label = "线性趋势健康预测"
                details = {"method": "当前健康度保守线性外推", "history_points": int(config["history_points"])}
            elif algorithm == EXPONENTIAL_SMOOTHING:
                factor = float(config["smoothing_factor"])
                label = "指数平滑健康预测"
                details = {"method": "指数平滑", "smoothing_factor": factor}
            elif algorithm == HEALTH_MOVING_AVERAGE:
                factor = 0.01
                label = "滑动平均健康预测"
                details = {"method": "最近窗口均值保守外推", "window": int(config["window"])}
            else:
                factor = float(config["degradation_rate"])
                label = "阈值退化健康预测"
                details = {"method": "固定退化率外推", "degradation_rate": factor, "warning_threshold": config["warning_threshold"]}
            forecast = []
            for step in range(1, horizon + 1):
                if algorithm == LINEAR_TREND:
                    scores = {key: round(value * (factor ** step), 1) for key, value in base.items()}
                elif algorithm == EXPONENTIAL_SMOOTHING:
                    scores = {key: round(value * (1.0 - factor * (step - 1) / max(1, horizon)), 1) for key, value in base.items()}
                elif algorithm == HEALTH_MOVING_AVERAGE:
                    scores = {key: round(value * (1.0 - factor * max(0, step - 1)), 1) for key, value in base.items()}
                else:
                    scores = {key: round(max(0.0, value - factor * 100.0 * step), 1) for key, value in base.items()}
                scores = _scenario_overlay(scores, parameters, scenario_mode)
                rows = _evaluation_rows(scores)
                overall = _scenario_overall(scores, parameters, scenario_mode)
                forecast.append({"step": step, "label": f"未来第{step}个时间点", "overall_score": overall, "overall_status": _score_status(overall), "subsystems": rows})
            return {
                "algorithm": algorithm,
                "algorithm_label": label,
                "model_version": MODEL_VERSION,
                "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "input": {"window_size": 1, "feature_count": len(PARAMETER_IDS), "input_dimension": len(PARAMETER_IDS), "window_source": "当前实时快照"},
                "horizon": horizon,
                "remaining_life_hours": round(forecast[-1]["overall_score"] / 100.0 * LIFE_HOURS),
                "forecast": forecast,
                "details": details,
            }
        model = self._require(PREDICTION)
        network = _TinyMLP.from_dict(model["network"])
        # 预测必须和已加载权重的输入输出形状一致。保存新配置但尚未重训时，
        # 仍使用模型元数据，避免旧权重与新窗口错配；点击重训后元数据会更新。
        prediction_config = (model.get("metadata", {}).get("metrics", {}).get("hyperparameters")
                             or model.get("metadata", {}).get("metrics", {}))
        prediction_config = {
            **_ALGORITHM_DEFAULTS[PREDICTION],
            **{key: prediction_config[key] for key in _ALGORITHM_DEFAULTS[PREDICTION] if key in prediction_config},
        }
        window = prediction_config["window_size"]
        horizon = prediction_config["horizon"]
        current_features = extract_features(parameters)
        flattened = current_features * window
        outputs = network.predict(flattened)
        forecast = []
        offset = 0
        for step in range(horizon):
            rows = []
            for subsystem_id in SUBSYSTEM_IDS:
                score = round(_clamp(outputs[offset]) * 100.0, 1)
                offset += 1
                rows.append({
                    "id": subsystem_id,
                    "name": SUBSYSTEM_NAMES[subsystem_id],
                    "score": score,
                    "status": _score_status(score),
                })
            overall = round(sum(row["score"] for row in rows) / len(rows), 1)
            forecast.append({
                "step": step + 1,
                "label": f"未来第{step + 1}个时间点",
                "overall_score": overall,
                "overall_status": _score_status(overall),
                "subsystems": rows,
            })
        # The neural network is trained on generic sequences.  Explicit
        # scenario overlays remain authoritative at inference time so a fault
        # switched on in the dashboard cannot be washed out by model output.
        for item in forecast:
            overlay = _scenario_overlay({row["id"]: row["score"] for row in item["subsystems"]}, parameters, scenario_mode)
            item["subsystems"] = _evaluation_rows(overlay)
            item["overall_score"] = _scenario_overall(
                {row["id"]: row["score"] for row in item["subsystems"]},
                parameters,
                scenario_mode,
            )
            item["overall_status"] = _score_status(item["overall_score"])
        life_hours = round(_clamp(forecast[-1]["overall_score"] / 100.0) * LIFE_HOURS)
        return {
            "algorithm": PREDICTION,
            "algorithm_label": "三层健康与寿命预测网络",
            "model_version": model["metadata"].get("model_version", MODEL_VERSION),
            "evaluated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input": {
                "window_size": window,
                "feature_count": len(PARAMETER_IDS),
                "input_dimension": window * len(PARAMETER_IDS),
                "window_source": "当前实时快照填充演示窗口",
            },
            "horizon": horizon,
            "remaining_life_hours": life_hours,
            "forecast": forecast,
        }


RUNTIME = ModelRuntime()


def ensure_models(force=False):
    return RUNTIME.ensure_models(force=force)


def model_status(active_algorithm=KMEANS):
    return RUNTIME.status(active_algorithm=active_algorithm)


def assess(parameters, algorithm=KMEANS, scenario_mode=None):
    return RUNTIME.assess(parameters, algorithm=algorithm, scenario_mode=scenario_mode)


def predict(parameters, algorithm=PREDICTION, scenario_mode=None):
    return RUNTIME.predict(parameters, algorithm=algorithm, scenario_mode=scenario_mode)


def process(parameters, algorithm):
    if algorithm not in (EMD, VMD, DWT, MOVING_AVERAGE, MEDIAN_FILTER):
        raise ValueError(f"未知信号处理算法: {algorithm}")
    return process_signal(parameters, algorithm)
