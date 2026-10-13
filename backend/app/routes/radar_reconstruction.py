"""雷达专用时序重构健康页面 API。

本蓝图提供模型状态、当前连续协议回放评估和测试集动态演示；模型本身还
通过通用健康算法目录和快照评估接口提供可选算法入口。
"""
from flask import Blueprint, jsonify, request

from ..radar_baselines import attach_baseline_series
from ..radar_depth_report import attach_depth_mttd_report
from ..radar_model_selection_report import attach_model_selection_report
from ..radar_openjev_decision import attach_openjev_trace
from ..radar_reconstruction import evaluate_live_snapshot, reconstruction_demo, runtime_status
from ..scenario import get_dashboard_payload

bp = Blueprint("radar_reconstruction", __name__)


def _source_metadata(record):
    return {
        "source_type": record.get("source_type"),
        "source_file": record.get("source_file"),
        "source_line_no": record.get("source_line_no"),
        "source_sequence": record.get("source_sequence"),
        "timestamp": record.get("timestamp"),
        "sequence": record.get("sequence"),
        "quality": record.get("source_quality"),
    }


@bp.get("/api/health/reconstruction/status")
def reconstruction_model_status():
    """返回专用时序健康页面展示的选中模型状态。"""
    try:
        return jsonify({"ok": True, "data": runtime_status()})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"重构模型状态读取失败: {exc}"}), 503


@bp.get("/api/health/reconstruction/evaluate")
def reconstruction_live_evaluation():
    """评估当前协议快照，并只使用其之前连续的 12 帧历史。"""
    snapshot = get_dashboard_payload()
    record = snapshot.get("scenario_record", {})
    parameters = snapshot.get("data", {}).get("health", {}).get("parameters", [])
    try:
        result = evaluate_live_snapshot(parameters, record)
        result["source"] = {**result.get("source", {}), **_source_metadata(record)}
        return jsonify({"ok": True, "data": result})
    except ValueError as exc:
        message = str(exc)
        if message.startswith("时序窗口预热中"):
            return jsonify({"ok": True, "data": None, "warming_up": message})
        return jsonify({"ok": False, "error": f"实时重构评估暂不可用: {message}"}), 503
    except Exception as exc:
        return jsonify({"ok": False, "error": f"实时重构评估失败: {exc}"}), 503


@bp.get("/api/health/reconstruction/demo")
def reconstruction_test_demo():
    """返回测试集动态重构序列，供专用时序健康页面播放。"""
    split = request.args.get("split", "test")
    try:
        limit = max(24, min(360, int(request.args.get("limit", "180"))))
        data = reconstruction_demo(split=split, limit=limit)
        data = attach_baseline_series(data)
        data = attach_depth_mttd_report(data)
        data = attach_model_selection_report(data)
        data = attach_openjev_trace(data)
        return jsonify({"ok": True, "data": data})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"测试集重构演示不可用: {exc}"}), 503
