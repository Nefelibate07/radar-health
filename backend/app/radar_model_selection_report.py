"""Expose the frozen, validation-selected Radar GAT comparison to the UI."""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .paths import get_project_root


REPORT_NAME = "radar_gat_selection_summary.json"
_CACHE: tuple[str, int, dict] | None = None
_LOCK = RLock()


def _report_path() -> Path:
    bundled = os.environ.get("RADAR_BUNDLED_RADAR_MODEL_DIR")
    if bundled:
        candidate = Path(bundled).expanduser() / REPORT_NAME
        if candidate.is_file():
            return candidate
    return get_project_root() / "backend" / "data" / "models" / "radar_gat" / REPORT_NAME


def load_model_selection_report() -> dict | None:
    """Load the packaged selection table, preferring the read-only app resource."""
    global _CACHE
    path = _report_path()
    if not path.is_file():
        return None
    modified = path.stat().st_mtime_ns
    cache_key = str(path.resolve())
    with _LOCK:
        if _CACHE and _CACHE[:2] == (cache_key, modified):
            return _CACHE[2]
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema_version") != "radar-gat-selection-summary-v1":
            raise ValueError("雷达模型选型摘要格式不兼容")
        candidates = report.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("雷达模型选型摘要缺少候选模型")
        _CACHE = (cache_key, modified, report)
        return report


def attach_model_selection_report(demo: dict) -> dict:
    return {**demo, "model_selection": load_model_selection_report()}
