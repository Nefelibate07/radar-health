"""Load the frozen multi-depth GAT injection-MTTD comparison for the demo page."""
from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .paths import get_backend_data_dir


REPORT_NAME = "radar_gat_depth_mttd.json"
_CACHE: tuple[str, int, dict] | None = None
_LOCK = RLock()


def _report_path() -> Path:
    bundled = os.environ.get("RADAR_BUNDLED_RADAR_DEPTH_MTTD_DIR")
    if bundled:
        path = Path(bundled).expanduser() / REPORT_NAME
        if path.is_file():
            return path
    return get_backend_data_dir() / "models" / "radar_gat_depth_sweep" / REPORT_NAME


def load_depth_mttd_report() -> dict | None:
    global _CACHE
    path = _report_path()
    if not path.is_file():
        return None
    modified = path.stat().st_mtime_ns
    key = str(path.resolve())
    with _LOCK:
        if _CACHE and _CACHE[:2] == (key, modified):
            return _CACHE[2]
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("schema_version") != "radar-gat-depth-mttd-v1":
            raise ValueError("GAT 层数 MTTD 报告格式不兼容")
        _CACHE = (key, modified, report)
        return report


def attach_depth_mttd_report(demo: dict) -> dict:
    """Expose the comparison alongside the synchronized normal-test replay."""
    return {**demo, "depth_mttd": load_depth_mttd_report()}
