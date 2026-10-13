"""Attach offline local Jev-style decision traces to the radar test replay.

The exploratory models are evaluated offline and are not loaded by the desktop
application. Only compact held-out traces and their experiment summaries are
shipped. Their candidate support is intentionally separate from the GAT health
score and is never interpreted as a calibrated fault probability.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .paths import get_backend_data_dir


TRACE_FILE = "radar_openjev_test_trace.json"
DEFAULT_MODEL = "minicpm5_1b"
MODEL_SPECS = {
    "minicpm5_1b": {
        "directory": Path("radar_openjev_small") / "minicpm5_1b",
        "label": "MiniCPM5-1B · MPS FP16",
    },
}
LABELS = [
    {"key": "stable", "label": "稳定正常", "color": "#62e6b2"},
    {"key": "mode_change", "label": "工况变化", "color": "#ffd166"},
    {"key": "persistent_deviation", "label": "持续偏离待核验", "color": "#ff7188"},
]
_CACHE: dict[str, Any] = {}


def _trace_path(model_key: str = DEFAULT_MODEL) -> Path:
    if model_key not in MODEL_SPECS:
        raise ValueError(f"未知的开源 Jev 型模型选项: {model_key}")
    relative_dir = MODEL_SPECS[model_key]["directory"]
    bundled_models = os.environ.get("RADAR_BUNDLED_MODEL_DIR")
    if bundled_models:
        candidate = Path(bundled_models) / relative_dir / TRACE_FILE
        if candidate.exists():
            return candidate
    return get_backend_data_dir() / "models" / relative_dir / TRACE_FILE


def _load_trace(model_key: str = DEFAULT_MODEL) -> dict | None:
    path = _trace_path(model_key)
    if not path.is_file():
        return None
    cache_key = f"{path}:{path.stat().st_mtime_ns}"
    if cache_key not in _CACHE:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") not in {
            "openjev-radar-nli-trace-v1",
            "semif-radar-direct-trace-v1",
        }:
            raise ValueError("Jev 型回放轨迹版本不受支持")
        if not isinstance(payload.get("points"), list):
            raise ValueError("OpenJev 回放轨迹缺少 points 列表")
        _CACHE[cache_key] = payload
    return _CACHE[cache_key]


def _experiment_summary(model_key: str) -> dict | None:
    trace_path = _trace_path(model_key)
    experiment_path = trace_path.parent / "semif_radar_experiment.json"
    if not experiment_path.is_file():
        return None
    return json.loads(experiment_path.read_text(encoding="utf-8"))


def _model_summary(model_key: str) -> dict:
    spec = MODEL_SPECS[model_key]
    trace = _load_trace(model_key)
    experiment = _experiment_summary(model_key)
    if trace is None or experiment is None:
        return {"key": model_key, "label": spec["label"], "ready": False}

    provenance = experiment.get("provenance", {})
    normal = experiment.get("test_normal", {})
    synthetic = experiment.get("test_controlled_synthetic", {})
    detected_events = sum(bool(item.get("detected")) for item in synthetic.get("by_event", []))
    return {
        "key": model_key,
        "label": spec["label"],
        "model": provenance.get("model"),
        "ready": True,
        "prompt_mode": experiment.get("selected_prompt_mode"),
        "local_forward_ms_median": provenance.get("local_test_trace_forward_ms_median"),
        "local_forward_ms_p95": provenance.get("local_test_trace_forward_ms_p95"),
        "test_normal_count": normal.get("count"),
        "test_normal_above_threshold_count": normal.get("above_validation_threshold_count"),
        "test_normal_above_threshold_rate": normal.get("above_validation_threshold_rate"),
        "synthetic_detected_event_count": detected_events,
        "synthetic_event_count": synthetic.get("event_count"),
        "synthetic_event_detection_rate": synthetic.get("event_detection_rate"),
    }


def attach_openjev_trace(data: dict, model_key: str = DEFAULT_MODEL) -> dict:
    """Join precomputed conditional option scores by source row index."""
    if model_key not in MODEL_SPECS:
        raise ValueError(f"未知的开源 Jev 型模型选项: {model_key}")
    summaries = [_model_summary(key) for key in MODEL_SPECS]
    trace = _load_trace(model_key)
    if data.get("split") != "test" or trace is None:
        data["openjev_decision"] = {
            "ready": False,
            "model_key": model_key,
            "available_models": [item for item in summaries if item["ready"]],
        }
        return data

    indexed = {int(item["source_index"]): item for item in trace["points"]}
    matched = 0
    for point in data.get("points", []):
        decision = indexed.get(int(point.get("source_index", -1)))
        if decision is not None:
            point["openjev_decision"] = decision
            matched += 1
    provenance = trace.get("provenance", {})
    experiment = _experiment_summary(model_key) or {}
    normal = experiment.get("test_normal", {})
    synthetic = experiment.get("test_controlled_synthetic", {})
    detected_events = sum(bool(item.get("detected")) for item in synthetic.get("by_event", []))
    data["openjev_decision"] = {
        "ready": matched > 0,
        "model_key": model_key,
        "model": provenance.get("model"),
        "revision": provenance.get("weights_revision", provenance.get("revision")),
        "benchmark": provenance.get("jevbench"),
        "local_forward_ms_median": provenance.get("local_test_trace_forward_ms_median"),
        "local_forward_ms_p95": provenance.get("local_test_trace_forward_ms_p95"),
        "test_normal_count": normal.get("count"),
        "test_normal_above_threshold_count": normal.get("above_validation_threshold_count"),
        "test_normal_above_threshold_rate": normal.get("above_validation_threshold_rate"),
        "synthetic_detected_event_count": detected_events,
        "synthetic_event_count": synthetic.get("event_count"),
        "synthetic_event_detection_rate": synthetic.get("event_detection_rate"),
        "prompt_mode": trace.get("prompt_mode"),
        "prompt_mode_label": "验证集选择：训练集 ICL" if trace.get("prompt_mode") == "train_icl" else "验证集选择：零样本",
        "sample_count": matched,
        "available_models": [item for item in summaries if item["ready"]],
        "labels": LABELS,
        "note": (
            "曲线是模型在给定三个选项中读取 A/B/C 原生决策分数后归一化的条件选项支持度，"
            "不是健康度、校准置信度、故障概率或物理故障判定；仅用于研究演示。"
            "测试集正常点越过验证阈值不等于已知真值下的误报，合成阶跃检出也不是现场故障召回率。"
        ),
    }
    return data
