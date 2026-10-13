"""Radar normal-replay baseline models and their held-out comparison traces."""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .paths import get_project_root


BASELINE_ARTIFACT_NAME = "radar_health_baseline_comparison.json"
BASELINE_SCHEMA_VERSION = "radar-health-baseline-comparison-v1"
_ARTIFACT_CACHE: tuple[str, int, dict] | None = None
_ARTIFACT_LOCK = RLock()


def _artifact_path() -> Path:
    bundled = os.environ.get("RADAR_BUNDLED_RADAR_BASELINE_DIR")
    if bundled:
        candidate = Path(bundled).expanduser() / BASELINE_ARTIFACT_NAME
        if candidate.is_file():
            return candidate
    local = get_project_root() / "backend" / "data" / "models" / "radar_baselines" / BASELINE_ARTIFACT_NAME
    return local


def load_baseline_comparison() -> dict:
    """Read the train-fitted baseline bundle, preferring the read-only app resource."""
    global _ARTIFACT_CACHE
    path = _artifact_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"雷达健康基线对照文件不存在：{path}；请先运行 backend/scripts/train_radar_baselines.py"
        )
    modified = path.stat().st_mtime_ns
    cache_key = str(path.resolve())
    with _ARTIFACT_LOCK:
        if _ARTIFACT_CACHE and _ARTIFACT_CACHE[:2] == (cache_key, modified):
            return _ARTIFACT_CACHE[2]
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("schema_version") != BASELINE_SCHEMA_VERSION:
            raise ValueError("雷达健康基线对照文件版本不兼容，请重新训练基线模型")
        _ARTIFACT_CACHE = (cache_key, modified, artifact)
        return artifact


def attach_baseline_series(demo: dict) -> dict:
    """Align six existing health baselines to the same sampled GAT test frames."""
    artifact = load_baseline_comparison()
    timestamps = artifact.get("test_timestamps") or []
    score_vectors = artifact.get("test_health_scores") or {}
    gat_points = demo.get("points") or []
    if not gat_points:
        raise ValueError("GAT 测试回放没有有效时序窗口，无法对齐基线曲线")

    metadata = artifact.get("metadata", {})
    primary_key = metadata.get("active_series_key", demo.get("primary_series_key", "gat5_vae"))
    primary_label = metadata.get("active_model_label", demo.get("model_label") or f"{demo.get('model') or 'GAT-5'} + GRU + VAE")
    series = [{
        "key": primary_key,
        "label": primary_label,
        "color": "#56ffc0",
        "training": "2026-07-19 至 24 训练；25 日验证标定",
        "points": [
            {"source_index": item["source_index"], "timestamp": item["timestamp"],
             "overall_score": item["overall_score"], "overall_status": item["overall_status"]}
            for item in gat_points
        ],
    }]

    for method in artifact.get("methods", []):
        key = method["key"]
        values = score_vectors.get(key)
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise ValueError(f"基线 {key} 的测试分数与测试时间序列长度不一致")
        points = []
        for item in gat_points:
            index = int(item["source_index"])
            if index < 0 or index >= len(timestamps) or timestamps[index] != item["timestamp"]:
                raise ValueError(f"基线 {key} 无法与 GAT 测试帧 {index} 对齐")
            score = float(values[index])
            points.append({
                "source_index": index,
                "timestamp": timestamps[index],
                "overall_score": round(score, 1),
                "overall_status": "正常" if score >= 60 else ("故障" if score >= 30 else "报废"),
            })
        series.append({**method, "points": points})

    return {
        **demo,
        "series": series,
        "primary_series_key": primary_key,
        "comparison_summary": artifact.get("comparison_summary", []),
        "comparison": artifact.get("comparison", {}),
    }
