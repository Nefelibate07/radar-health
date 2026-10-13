"""算法管理配置接口。

配置项由后端定义，前端只负责编辑和展示。这样界面上的每一行参数都
有明确的类型、范围和持久化位置，重训时模型运行时会重新读取这些值。
"""
import math

from flask import Blueprint, jsonify, request

from .. import db
from ..model_runtime import (
    DWT, EMD, EXPONENTIAL_SMOOTHING, KMEANS, LINEAR_TREND, PREDICTION,
    SOM, STATISTICAL, VMD, WEIGHTED_DISTANCE, THRESHOLD_VOTING,
    FUZZY_COMPREHENSIVE, HEALTH_MOVING_AVERAGE, THRESHOLD_PROJECTION,
    MOVING_AVERAGE, MEDIAN_FILTER,
)
from ..radar_reconstruction import GAT_RECONSTRUCTION

bp = Blueprint("algorithms", __name__)

# 一个参数对应一个条目。key 同时也是训练函数使用的配置名。
PARAMETER_DEFINITIONS = {
    "kmeans": [
        {"key": "cluster_count", "label": "聚类中心数 K", "type": "number", "min": 2, "max": 8, "step": 1, "default": 3},
        {"key": "iterations", "label": "最大迭代次数", "type": "number", "min": 1, "max": 100, "step": 1, "default": 16},
    ],
    "som": [
        {"key": "rows", "label": "拓扑网格行数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "cols", "label": "拓扑网格列数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "epochs", "label": "训练轮数", "type": "number", "min": 1, "max": 100, "step": 1, "default": 12},
        {"key": "learning_rate", "label": "初始学习率", "type": "number", "min": 0.01, "max": 1, "step": 0.01, "default": 0.32},
    ],
    "mlp_predictor": [
        {"key": "window_size", "label": "输入时间窗口", "type": "number", "min": 2, "max": 12, "step": 1, "default": 6},
        {"key": "horizon", "label": "预测时间点数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "hidden_units", "label": "隐藏层神经元数", "type": "number", "min": 2, "max": 32, "step": 1, "default": 10},
        {"key": "epochs", "label": "训练轮数", "type": "number", "min": 1, "max": 300, "step": 1, "default": 100},
        {"key": "learning_rate", "label": "网络学习率", "type": "number", "min": 0.01, "max": 1, "step": 0.01, "default": 0.25},
    ],
    STATISTICAL: [{"key": "warning_threshold", "label": "健康告警阈值", "type": "number", "min": 30, "max": 90, "step": 1, "default": 60}],
    WEIGHTED_DISTANCE: [{"key": "distance_scale", "label": "距离衰减尺度", "type": "number", "min": 0.1, "max": 1, "step": 0.01, "default": 0.45}],
    THRESHOLD_VOTING: [{"key": "warning_threshold", "label": "健康投票阈值", "type": "number", "min": 30, "max": 90, "step": 1, "default": 60}],
    FUZZY_COMPREHENSIVE: [{"key": "membership_slope", "label": "隶属度平滑系数", "type": "number", "min": 0.5, "max": 3, "step": 0.1, "default": 1.5}],
    LINEAR_TREND: [
        {"key": "horizon", "label": "预测时间点数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "history_points", "label": "趋势参考点数", "type": "number", "min": 2, "max": 48, "step": 1, "default": 12},
    ],
    EXPONENTIAL_SMOOTHING: [
        {"key": "horizon", "label": "预测时间点数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "smoothing_factor", "label": "平滑系数 α", "type": "number", "min": 0.05, "max": 0.95, "step": 0.01, "default": 0.35},
    ],
    HEALTH_MOVING_AVERAGE: [
        {"key": "horizon", "label": "预测时间点数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "window", "label": "平滑窗口", "type": "number", "min": 2, "max": 12, "step": 1, "default": 6},
    ],
    THRESHOLD_PROJECTION: [
        {"key": "horizon", "label": "预测时间点数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3},
        {"key": "degradation_rate", "label": "单步退化率", "type": "number", "min": 0.001, "max": 0.2, "step": 0.001, "default": 0.015},
        {"key": "warning_threshold", "label": "预警阈值", "type": "number", "min": 30, "max": 90, "step": 1, "default": 60},
    ],
    EMD: [{"key": "envelope_window", "label": "包络滑动窗口", "type": "number", "min": 2, "max": 20, "step": 1, "default": 5}],
    VMD: [
        {"key": "mode_count", "label": "模态数量 K", "type": "number", "min": 2, "max": 6, "step": 1, "default": 3},
        {"key": "iterations", "label": "优化迭代次数", "type": "number", "min": 1, "max": 50, "step": 1, "default": 8},
    ],
    DWT: [{"key": "decomposition_level", "label": "分解层数", "type": "number", "min": 1, "max": 6, "step": 1, "default": 3}],
    MOVING_AVERAGE: [{"key": "window", "label": "滑动平均窗口", "type": "number", "min": 2, "max": 20, "step": 1, "default": 5}],
    MEDIAN_FILTER: [{"key": "window", "label": "中值滤波窗口", "type": "number", "min": 3, "max": 9, "step": 2, "default": 5}],
}
IMPLEMENTED = {key: [item["key"] for item in definitions] for key, definitions in PARAMETER_DEFINITIONS.items()}
DEFAULTS = {
    key: {item["key"]: item["default"] for item in definitions}
    for key, definitions in PARAMETER_DEFINITIONS.items()
}
CATEGORIES = {"数据处理算法", "健康评估算法", "健康预测算法"}

ALGORITHM_CATALOG = [
    {"key": EMD, "name": "EMD分解", "category": "数据处理算法", "description": "用滑动包络分解健康特征的趋势与残差。", "implemented": True, "endpoint": "/api/health/process"},
    {"key": VMD, "name": "VMD分解", "category": "数据处理算法", "description": "按多尺度差分构造带限模态，观察参数变化成分。", "implemented": True, "endpoint": "/api/health/process"},
    {"key": DWT, "name": "离散小波变换", "category": "数据处理算法", "description": "以多尺度差分提取瞬态变化和近似趋势。", "implemented": True, "endpoint": "/api/health/process"},
    {"key": KMEANS, "name": "K-Means监测", "category": "健康评估算法", "description": "聚类识别设备状态并输出子系统健康度。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": SOM, "name": "SOM监测", "category": "健康评估算法", "description": "用拓扑映射识别状态漂移和异常区域。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": STATISTICAL, "name": "统计基线评估", "category": "健康评估算法", "description": "对子系统参数健康特征取均值，提供可解释基线。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": WEIGHTED_DISTANCE, "name": "加权距离评估", "category": "健康评估算法", "description": "按参数偏离健康基线的距离进行指数衰减评分。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": THRESHOLD_VOTING, "name": "阈值投票评估", "category": "健康评估算法", "description": "统计参数跨越健康阈值的比例，适合快速告警筛查。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": FUZZY_COMPREHENSIVE, "name": "模糊综合评估", "category": "健康评估算法", "description": "用平滑隶属度综合边界附近的连续健康特征。", "implemented": True, "endpoint": "/api/health/evaluate"},
    {"key": GAT_RECONSTRUCTION, "name": "GAT-5 多源时序重构", "category": "健康评估算法", "description": "专用映射、模型和数据未公开，当前版本不提供此算法。", "implemented": False, "endpoint": "/api/health/evaluate"},
    {"key": PREDICTION, "name": "三层网络预测", "category": "健康预测算法", "description": "基于实时特征窗口预测未来健康度和剩余寿命。", "implemented": True, "endpoint": "/api/health/predict"},
    {"key": LINEAR_TREND, "name": "线性趋势预测", "category": "健康预测算法", "description": "依据当前健康度趋势做轻量外推。", "implemented": True, "endpoint": "/api/health/predict"},
    {"key": EXPONENTIAL_SMOOTHING, "name": "指数平滑预测", "category": "健康预测算法", "description": "以平滑系数抑制短期波动并预测后续健康度。", "implemented": True, "endpoint": "/api/health/predict"},
    {"key": HEALTH_MOVING_AVERAGE, "name": "滑动平均预测", "category": "健康预测算法", "description": "用最近窗口均值抑制回放噪声后外推健康度。", "implemented": True, "endpoint": "/api/health/predict"},
    {"key": THRESHOLD_PROJECTION, "name": "阈值退化预测", "category": "健康预测算法", "description": "按可解释退化率外推，并估计达到预警阈值的时间。", "implemented": True, "endpoint": "/api/health/predict"},
    {"key": MOVING_AVERAGE, "name": "滑动平均滤波", "category": "数据处理算法", "description": "提取健康特征的局部趋势并计算残差。", "implemented": True, "endpoint": "/api/health/process"},
    {"key": MEDIAN_FILTER, "name": "中值滤波", "category": "数据处理算法", "description": "抑制孤立尖峰，适合协议参数异常点预处理。", "implemented": True, "endpoint": "/api/health/process"},
]


def _definition(key):
    return PARAMETER_DEFINITIONS[key]


def _read_config(key):
    stored = db.get_algorithm_config(key) or {}
    values = {}
    for item in _definition(key):
        raw = stored.get(item["key"], item["default"])
        try:
            value = float(raw)
            if not math.isfinite(value) or not _is_valid_step(item, value):
                raise ValueError
        except (TypeError, ValueError):
            value = item["default"]
        if item["step"] == 1:
            value = int(round(value))
        values[item["key"]] = max(item["min"], min(item["max"], value))
    return values


def _is_valid_step(item, number):
    """判断参数是否落在定义的离散步长上。

    HTML 的 ``step`` 属性只能改善浏览器端输入体验，不能作为后端安全/业务
    校验。以最小值为步长基准，允许极小的浮点误差，避免 0.3 这类合法小数
    因二进制浮点表示被误判；同时明确拒绝整数参数的小数值和不符合步长的值。
    """
    step = float(item.get("step") or 0)
    if step <= 0:
        return True
    quotient = (number - float(item["min"])) / step
    return math.isclose(quotient, round(quotient), rel_tol=0.0, abs_tol=1e-9)


def _validate_config(key, payload):
    if not isinstance(payload, dict):
        raise ValueError("参数必须是对象")
    values = {}
    for item in _definition(key):
        name = item["key"]
        if name not in payload:
            value = _read_config(key)[name]
        else:
            raw = payload[name]
            if isinstance(raw, bool):
                raise ValueError(f"{item['label']}必须是数字")
            try:
                number = float(raw)
            except (TypeError, ValueError):
                raise ValueError(f"{item['label']}必须是数字")
            if not math.isfinite(number):
                raise ValueError(f"{item['label']}必须是有限数字")
            if not item["min"] <= number <= item["max"]:
                raise ValueError(f"{item['label']}必须在 {item['min']} 到 {item['max']} 之间")
            if not _is_valid_step(item, number):
                if item["step"] == 1:
                    raise ValueError(f"{item['label']}必须是整数")
                raise ValueError(f"{item['label']}必须按 {item['step']} 的步长填写")
            value = int(round(number)) if item["step"] == 1 else round(number, 4)
        values[name] = value
    # 1x1 SOM 只有一个神经元时，运行时仍然可以工作，但没有聚类意义；
    # 保持允许配置，便于演示参数变化，不额外增加业务限制。
    return values


@bp.get("/api/algorithms/config")
def configs():
    result = {}
    for key, definitions in PARAMETER_DEFINITIONS.items():
        values = _read_config(key)
        result[key] = {
            "key": key,
            "implemented": True,
            "params": [
                {**{field: item[field] for field in ("key", "label", "type", "min", "max", "step")}, "value": values[item["key"]], "implemented": True}
                for item in definitions
            ],
        }
    return jsonify({"ok": True, "data": result})


@bp.get("/api/algorithms/catalog")
def catalog():
    return jsonify({"ok": True, "data": ALGORITHM_CATALOG})


@bp.post("/api/algorithms/config/<key>")
def save_config(key):
    if key not in IMPLEMENTED:
        return jsonify({"ok": False, "error": "算法尚未接入"}), 400
    payload = request.get_json(silent=True) or {}
    params = payload.get("params") if isinstance(payload.get("params"), (dict, list)) else payload
    # 兼容前端提交 [{key,value}] 的条目形式，同时也接受 {key:value}。
    if isinstance(params, list):
        params = {item.get("key"): item.get("value") for item in params if isinstance(item, dict)}
    try:
        values = _validate_config(key, params)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    db.save_algorithm_config(key, values)
    return jsonify({"ok": True, "key": key, "params": values, "requires_retrain": True})


@bp.get("/api/algorithms/custom")
def custom_list():
    return jsonify({"ok": True, "data": db.list_custom_algorithms()})


@bp.post("/api/algorithms/custom")
def custom_add():
    payload = request.get_json(silent=True) or {}
    missing = [key for key in ("name", "category", "file_path", "config_path") if not str(payload.get(key, "")).strip()]
    if missing or payload.get("category") not in CATEGORIES:
        return jsonify({"ok": False, "error": "自定义算法字段不完整或类别无效"}), 400
    return jsonify({"ok": True, "data": db.add_custom_algorithm(payload["name"], payload["category"], payload["file_path"], payload["config_path"])})


@bp.delete("/api/algorithms/custom/<int:algorithm_id>")
def custom_delete(algorithm_id):
    db.delete_custom_algorithm(algorithm_id)
    return jsonify({"ok": True})
