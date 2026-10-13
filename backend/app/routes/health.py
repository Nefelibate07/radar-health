"""健康算法、训练、实时评估和健康预测接口。

路由层只负责取当前场景快照和组织响应，算法实现集中在 ``model_runtime.py``，
这样以后把合成数据换成真实采集数据时，不需要改前端契约。
"""
from flask import Blueprint, jsonify, request

from .. import db
from ..model_runtime import (
    KMEANS,
    PREDICTION,
    SOM,
    STATISTICAL,
    WEIGHTED_DISTANCE,
    LINEAR_TREND,
    EXPONENTIAL_SMOOTHING,
    EMD,
    VMD,
    DWT,
    THRESHOLD_VOTING,
    FUZZY_COMPREHENSIVE,
    HEALTH_MOVING_AVERAGE,
    THRESHOLD_PROJECTION,
    MOVING_AVERAGE,
    MEDIAN_FILTER,
    assess,
    ensure_models,
    model_status,
    process,
    predict,
)
from ..radar_reconstruction import GAT_RECONSTRUCTION, evaluate_live_snapshot, runtime_status as radar_reconstruction_status
from ..scenario import get_dashboard_payload

bp = Blueprint("health", __name__)

MODEL_ALGORITHMS = {KMEANS, SOM, STATISTICAL, WEIGHTED_DISTANCE, THRESHOLD_VOTING, FUZZY_COMPREHENSIVE, GAT_RECONSTRUCTION}
PREDICTION_ALGORITHMS = {"mlp_predictor", LINEAR_TREND, EXPONENTIAL_SMOOTHING, HEALTH_MOVING_AVERAGE, THRESHOLD_PROJECTION}
PROCESS_ALGORITHMS = {EMD, VMD, DWT, MOVING_AVERAGE, MEDIAN_FILTER}
VALID_ALGORITHMS = MODEL_ALGORITHMS
DEFAULT_ALGORITHM = KMEANS


def _current_health(algorithm):
    snapshot = get_dashboard_payload()
    record = snapshot.get("scenario_record", {})
    if algorithm == GAT_RECONSTRUCTION:
        result = evaluate_live_snapshot(
            snapshot.get("data", {}).get("health", {}).get("parameters", []), record
        )
        result["source"] = _source_metadata(record)
        return result
    if algorithm in MODEL_ALGORITHMS:
        result = assess(_current_parameters(), algorithm=algorithm, scenario_mode=record.get("mode"))
        result["source"] = _source_metadata(record)
        return result

    raise ValueError(f"未知算法: {algorithm}")


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


@bp.get("/api/health/algorithm")
def get_algorithm():
    algorithm = db.get_setting("health_algorithm", DEFAULT_ALGORITHM)
    if algorithm not in VALID_ALGORITHMS:
        algorithm = DEFAULT_ALGORITHM
    data = None if algorithm == GAT_RECONSTRUCTION else _current_health(algorithm)
    return jsonify({"algorithm": algorithm, "data": data})


@bp.post("/api/health/algorithm")
def set_algorithm():
    payload = request.get_json(silent=True) or {}
    algorithm = payload.get("algorithm")
    if algorithm not in VALID_ALGORITHMS:
        return jsonify({"error": f"未知算法: {algorithm}"}), 400
    db.set_setting("health_algorithm", algorithm)
    if algorithm == GAT_RECONSTRUCTION:
        return jsonify({"ok": True, "algorithm": algorithm, "data": None})
    return jsonify({"ok": True, "algorithm": algorithm, "data": _current_health(algorithm)})


@bp.get("/api/health/models")
def get_models():
    """返回算法中心全部可用算法的运行状态。"""
    algorithm = db.get_setting("health_algorithm", DEFAULT_ALGORITHM)
    if algorithm not in VALID_ALGORITHMS:
        algorithm = DEFAULT_ALGORITHM
    try:
        ensure_models()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "data": {"active_algorithm": algorithm}}), 503
    status = model_status(active_algorithm=algorithm)
    temporal_status = radar_reconstruction_status()
    status.setdefault("models", {})[GAT_RECONSTRUCTION] = {
        "trained": bool(temporal_status.get("ready")),
        "model_version": temporal_status.get("model"),
        "model_family": temporal_status.get("model_family"),
        "storage_source": "bundled" if "Resources" in str(temporal_status.get("model_dir", "")) else "local",
    }
    status["algorithms"] = sorted(MODEL_ALGORITHMS | PREDICTION_ALGORITHMS | PROCESS_ALGORITHMS)
    status["source"] = _source_metadata(get_dashboard_payload().get("scenario_record", {}))
    return jsonify({"ok": True, "data": status})


@bp.post("/api/health/retrain")
def retrain():
    # 训练规模刻意保持很小，按钮点击后同步返回，便于现场演示和排错。
    try:
        status = ensure_models(force=True)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"模型重训失败: {exc}"}), 500
    return jsonify({
        "ok": True,
        "message": "K-Means、SOM 和三层预测网络已完成重训；其余算法为实时确定性计算",
        "data": status,
    })


def _current_parameters():
    payload = get_dashboard_payload()
    return payload.get("data", {}).get("health", {}).get("parameters", [])


@bp.get("/api/health/evaluate")
def evaluate_current_snapshot():
    algorithm = request.args.get("algorithm") or db.get_setting("health_algorithm", DEFAULT_ALGORITHM)
    if algorithm not in VALID_ALGORITHMS:
        return jsonify({"ok": False, "error": f"未知评估算法: {algorithm}"}), 400
    try:
        result = _current_health(algorithm)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("时序窗口预热中"):
            return jsonify({"ok": True, "data": None, "warming_up": message})
        return jsonify({"ok": False, "error": f"健康评估失败: {message}"}), 503
    except Exception as exc:
        return jsonify({"ok": False, "error": f"健康评估失败: {exc}"}), 503
    return jsonify({"ok": True, "data": result})


@bp.get("/api/health/process")
def process_current_snapshot():
    algorithm = request.args.get("algorithm")
    if algorithm not in PROCESS_ALGORITHMS:
        return jsonify({"ok": False, "error": f"未知信号处理算法: {algorithm}"}), 400
    try:
        result = process(_current_parameters(), algorithm)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"信号处理失败: {exc}"}), 503
    return jsonify({"ok": True, "data": result})


@bp.get("/api/health/prediction")
def prediction_status():
    """给算法中心一个不执行推理的预测模型状态入口。"""
    try:
        ensure_models()
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    algorithm = db.get_setting("health_algorithm", DEFAULT_ALGORITHM)
    if algorithm not in VALID_ALGORITHMS:
        algorithm = DEFAULT_ALGORITHM
    status = model_status(active_algorithm=algorithm)
    temporal_status = radar_reconstruction_status()
    status.setdefault("models", {})[GAT_RECONSTRUCTION] = {
        "trained": bool(temporal_status.get("ready")),
        "model_version": temporal_status.get("model"),
        "model_family": temporal_status.get("model_family"),
        "storage_source": "bundled" if "Resources" in str(temporal_status.get("model_dir", "")) else "local",
    }
    status["algorithms"] = sorted(MODEL_ALGORITHMS | PREDICTION_ALGORITHMS | PROCESS_ALGORITHMS)
    status["source"] = _source_metadata(get_dashboard_payload().get("scenario_record", {}))
    return jsonify({"ok": True, "data": status})


@bp.route("/api/health/predict", methods=["GET", "POST"])
def predict_current_snapshot():
    """用当前实时快照填充演示窗口，输出未来 3 个时间点和剩余寿命。"""
    # 请求体仅保留兼容性，不接受客户端另造的参数作为正式模型输入；模型输入
    # 必须来自 ScenarioEngine 当前合成演示快照快照。
    request.get_json(silent=True)
    parameters = _current_parameters()
    record = get_dashboard_payload().get("scenario_record", {})
    try:
        algorithm = request.args.get("algorithm") or PREDICTION
        if algorithm not in PREDICTION_ALGORITHMS:
            return jsonify({"ok": False, "error": f"未知预测算法: {algorithm}"}), 400
        result = predict(parameters, algorithm=algorithm, scenario_mode=record.get("mode"))
    except Exception as exc:
        return jsonify({"ok": False, "error": f"健康预测失败: {exc}"}), 503
    result["source"] = _source_metadata(record)
    return jsonify({"ok": True, "data": result})


@bp.get("/api/health/daily-report")
def daily_report():
    # 直接从唯一实时源的持久化快照取最近 48 个点；不再回退到随机 daily_scores 种子。
    with db.get_health_conn() as conn:
        rows = conn.execute(
            "SELECT sequence, timestamp, overall_score, overall_status, source_type, source_file, source_line_no, source_sequence "
            "FROM scenario_snapshots ORDER BY sequence DESC LIMIT 48"
        ).fetchall()
    rows = list(reversed(rows))
    data = [
        {
            "date": r["timestamp"],
            "display_date": r["timestamp"][5:16],
            "score": r["overall_score"],
            "status": r["overall_status"],
            "fault_count": 1 if r["overall_status"] != "正常" else 0,
            "sequence": r["sequence"],
            "source_type": r["source_type"],
            "source_file": r["source_file"],
            "source_line_no": r["source_line_no"],
            "source_sequence": r["source_sequence"],
        }
        for r in rows
    ]

    today_score = data[-1]["score"] if data else None
    average_score = round(sum(r["score"] for r in data) / len(data), 1) if data else None

    return jsonify({
        "data": data,
        "summary": {"today_score": today_score, "average_score": average_score},
    })
