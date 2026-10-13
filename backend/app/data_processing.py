"""Live signal processing and per-signal configuration for the monitoring UI."""
import json
import math
import statistics
from collections import Counter

from . import db
from .paths import get_config_dir
from .scenario import get_dashboard_payload
from .subsystems import SUBSYSTEMS

SETTING_KEY = "signal_processing_config"


def _catalog():
    with open(get_config_dir() / "signal_processing.json", encoding="utf-8") as source:
        return json.load(source)


def _metadata_by_id():
    return {
        parameter["id"]: {**parameter, "subsystem_id": subsystem["id"], "subsystem": subsystem["name"]}
        for subsystem in SUBSYSTEMS
        for parameter in subsystem.get("params", [])
    }


def _auto_category(parameter):
    if parameter.get("dtype") == "enum":
        return "discrete"
    unit = str(parameter.get("unit") or "").strip().lower()
    name = str(parameter.get("name") or "")
    if unit in {"a", "ma"} or "电流" in name:
        return "current"
    if unit in {"v", "mv", "kv"} or "电压" in name:
        return "voltage"
    if unit in {"°", "deg", "degree"} or "角" in name:
        return "angle"
    raw_type = str(parameter.get("raw_type") or "").upper()
    if "INT" in raw_type or raw_type.startswith(("I", "U")):
        return "integer"
    if parameter.get("dtype") in {"int", "integer"}:
        return "integer"
    if parameter.get("dtype") in {"float", "double", "number"}:
        return "float"
    return "other"


def _saved_config():
    raw = db.get_setting(SETTING_KEY)
    if not raw:
        return {}
    try:
        result = json.loads(raw)
        return result if isinstance(result, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def _effective_threshold(parameter, overrides):
    if parameter["id"] in overrides:
        value = overrides[parameter["id"]]
        if value.get("enabled") is False:
            return None, "未配置"
        low, high = value.get("minimum"), value.get("maximum")
        if low is None and high is None:
            return None, "未配置"
        return {"minimum": low, "maximum": high}, "用户配置"
    value_range = parameter.get("range")
    if isinstance(value_range, list) and len(value_range) == 2:
        return {"minimum": value_range[0], "maximum": value_range[1]}, "参数字典"
    return None, "未配置"


def _format_value(value, metadata):
    if value is None:
        return "--"
    enum = metadata.get("enum") or {}
    if metadata.get("dtype") == "enum":
        try:
            key = str(int(value))
        except (TypeError, ValueError):
            key = str(value)
        return str(enum.get(key, value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    precision = metadata.get("precision")
    digits = 3 if isinstance(precision, (int, float)) and precision < 0.01 else (1 if precision else 2)
    return f"{number:.{digits}f}"


def _history_by_param(current_parameters, current_sequence, limit):
    history = {}
    for item in current_parameters:
        param_id = str(item.get("param_id") or "")
        if param_id and item.get("value") is not None:
            history[param_id] = [item["value"]]
    seen_sequences = {current_sequence} if current_sequence is not None else set()
    try:
        with db.get_conn() as conn:
            rows = conn.execute(
                "SELECT sequence, payload_json FROM scenario_snapshots ORDER BY sequence DESC LIMIT ?",
                (max(limit * 2, 12),),
            ).fetchall()
        for row in rows:
            if row["sequence"] in seen_sequences:
                continue
            payload = json.loads(row["payload_json"])
            parameters = payload.get("data", {}).get("health", {}).get("parameters", [])
            for item in parameters:
                param_id = str(item.get("param_id") or "")
                if param_id and item.get("value") is not None and len(history.get(param_id, [])) < limit:
                    history.setdefault(param_id, []).append(item["value"])
            seen_sequences.add(row["sequence"])
            if history and all(len(values) >= limit for values in history.values()):
                break
    except Exception:
        # A first-run database may not contain snapshots yet; current value still works.
        pass
    return history


def _apply_method(values_newest_first, method, window, alpha):
    values = list(reversed(values_newest_first[:window]))
    if not values:
        return None
    if method == "none":
        return values[-1]
    if method == "majority":
        counts = Counter(str(item) for item in values)
        winner = counts.most_common(1)[0][0]
        return next((item for item in values if str(item) == winner), values[-1])
    numeric = []
    for value in values:
        try:
            number = float(value)
            if math.isfinite(number):
                numeric.append(number)
        except (TypeError, ValueError):
            continue
    if not numeric:
        return values[-1]
    if method == "moving_average":
        return sum(numeric) / len(numeric)
    if method == "median":
        return statistics.median(numeric)
    if method == "exponential":
        result = numeric[0]
        for value in numeric[1:]:
            result = alpha * value + (1 - alpha) * result
        return result
    if method == "circular_average":
        sin_mean = sum(math.sin(math.radians(item)) for item in numeric) / len(numeric)
        cos_mean = sum(math.cos(math.radians(item)) for item in numeric) / len(numeric)
        return math.degrees(math.atan2(sin_mean, cos_mean)) % 360
    if method == "round":
        return round(numeric[-1])
    return values[-1]


def _signal_state(item, processed_value, threshold, metadata):
    if item.get("value") is None:
        return "无数据", "unknown", "当前快照没有测点值"
    if str(item.get("source_type") or "").endswith("_fault_injected"):
        # Fault scenarios deliberately replace mapped replay values. Preserve
        # that explicit simulation signal in diagnosis even when an enum such
        # as "限位" is not a real-world alarm by itself, or a numeric point
        # has no configured engineering threshold. The reason keeps this
        # distinct from a fault proven by live measurement limits.
        if metadata.get("dtype") == "enum":
            return "状态告警", "fault", "场景注入故障状态（模拟值）"
        return "越限", "fault", "场景注入越限（模拟值，非实时阈值判据）"
    if metadata.get("dtype") == "enum":
        label = str(item.get("enum_label") or _format_value(processed_value, metadata))
        name = str(metadata.get("name") or "")
        is_power_status = any(word in name for word in ("加电", "供电", "电源"))
        bad_words = ("告警", "失锁", "不到位", "异常", "故障", "失步", "过热", "掉电")
        bad = any(word in label for word in bad_words) and not any(word in label for word in ("未告警", "未故障"))
        if is_power_status and any(word in label for word in ("去电", "断开", "掉电")):
            bad = True
        if "未限位" in label or label.startswith("未"):
            bad = False
        return ("状态告警", "fault", label) if bad else ("正常", "normal", label)
    if threshold is None:
        return "待配置阈值", "unknown", "参数字典未提供数值范围"
    try:
        value = float(processed_value)
    except (TypeError, ValueError):
        return "待检查", "unknown", "当前值无法转换为数值"
    low, high = threshold.get("minimum"), threshold.get("maximum")
    precision = metadata.get("precision")
    tolerance = max(0.01, float(precision or 0) * 2)
    # Some protocol angle ranges are stored as a signed near-full-turn range
    # (for example -350°..350°) while live samples use 0°..360°. Compare the
    # equivalent signed angle at the wrap boundary to avoid a false alarm at 0°.
    if metadata.get("unit") == "°" and low is not None and high is not None and float(low) < 0 < float(high) and float(high) >= 180:
        wrapped = (value + 180) % 360 - 180
        if float(low) - tolerance <= wrapped <= float(high) + tolerance:
            return "正常", "normal", "角度周期归一化后在配置范围内"
    if low is not None and value < float(low) - tolerance:
        return "越限", "fault", f"处理值低于下限 {low}"
    if high is not None and value > float(high) + tolerance:
        return "越限", "fault", f"处理值高于上限 {high}"
    return "正常", "normal", "处理值在配置范围内"


def get_processing_snapshot():
    catalog = _catalog()
    saved = _saved_config()
    metadata_by_id = _metadata_by_id()
    categories = {item["id"]: item for item in catalog["categories"]}
    method_overrides = saved.get("category_methods", {})
    category_overrides = saved.get("signal_categories", {})
    threshold_overrides = saved.get("signal_thresholds", {})
    snapshot = get_dashboard_payload()
    record = snapshot.get("scenario_record", {})
    parameters = snapshot.get("data", {}).get("health", {}).get("parameters", [])
    max_window = max(
        [catalog.get("default_window", 5)]
        + [int(item.get("window", catalog.get("default_window", 5))) for item in method_overrides.values() if isinstance(item, dict)]
    )
    history = _history_by_param(parameters, record.get("sequence"), max_window)
    signals = []
    for item in parameters:
        param_id = str(item.get("param_id") or "")
        metadata = metadata_by_id.get(param_id, {
            "id": param_id, "name": item.get("name"), "dtype": item.get("dtype"),
            "unit": item.get("unit", ""), "range": None, "precision": None, "enum": {},
        })
        auto_category = _auto_category(metadata)
        category_id = category_overrides.get(param_id, auto_category)
        if category_id not in categories:
            category_id = auto_category if auto_category in categories else "other"
        category = categories[category_id]
        method_config = {"method": category.get("default_method", "none"), "window": catalog.get("default_window", 5), "alpha": catalog.get("default_alpha", 0.3)}
        method_config.update(method_overrides.get(category_id, {}))
        if method_config.get("method") not in category.get("methods", []):
            method_config["method"] = category.get("default_method", "none")
        window = max(1, min(101, int(method_config.get("window", catalog.get("default_window", 5)))))
        alpha = max(0.01, min(1.0, float(method_config.get("alpha", catalog.get("default_alpha", 0.3)))))
        threshold, threshold_source = _effective_threshold(metadata, threshold_overrides)
        values = history.get(param_id, [item.get("value")])
        processed = _apply_method(values, method_config["method"], window, alpha)
        status, severity, reason = _signal_state(item, processed, threshold, metadata)
        low = threshold.get("minimum") if threshold else None
        high = threshold.get("maximum") if threshold else None
        signals.append({
            "id": param_id,
            "snapshot_id": item.get("id"),
            "name": item.get("name"),
            "subsystem_id": item.get("subsystem_id"),
            "subsystem": item.get("subsystem"),
            "dtype": item.get("dtype"),
            "unit": item.get("unit", ""),
            "current_value": item.get("value"),
            "current_display": item.get("display_value", _format_value(item.get("value"), metadata)),
            "processed_value": processed,
            "processed_display": _format_value(processed, metadata),
            "category": category_id,
            "category_name": category["name"],
            "auto_category": auto_category,
            "method": method_config["method"],
            "method_name": next((x["name"] for x in catalog["algorithms"] if x["id"] == method_config["method"]), method_config["method"]),
            "threshold": threshold,
            "threshold_minimum": low,
            "threshold_maximum": high,
            "threshold_source": threshold_source,
            "enum": metadata.get("enum") or {},
            "status": status,
            "severity": severity,
            "reason": reason,
            "source_type": item.get("source_type"),
        })
    return {
        "ok": True,
        "data": {
            "timestamp": record.get("timestamp"),
            "sequence": record.get("sequence"),
            "source_type": record.get("source_type"),
            "mode": record.get("mode"),
            "mode_label": record.get("mode_label"),
            "categories": catalog["categories"],
            "algorithms": catalog["algorithms"],
            "category_methods": method_overrides,
            "signal_categories": category_overrides,
            "signal_thresholds": threshold_overrides,
            "settings": {"window": catalog.get("default_window", 5), "alpha": catalog.get("default_alpha", 0.3)},
            "signals": signals,
        },
    }


def save_processing_config(payload):
    catalog = _catalog()
    categories = {item["id"]: item for item in catalog["categories"]}
    known_params = set(_metadata_by_id())
    current = _saved_config()
    category_methods = dict(current.get("category_methods", {}))
    signal_categories = dict(current.get("signal_categories", {}))
    signal_thresholds = dict(current.get("signal_thresholds", {}))

    incoming_methods = payload.get("category_methods", {})
    if not isinstance(incoming_methods, dict):
        raise ValueError("category_methods 必须是对象")
    for category_id, config in incoming_methods.items():
        if category_id not in categories or not isinstance(config, dict):
            raise ValueError(f"未知数据类别: {category_id}")
        method = config.get("method", categories[category_id].get("default_method", "none"))
        if method not in categories[category_id].get("methods", []):
            raise ValueError(f"{categories[category_id]['name']} 不支持处理方法 {method}")
        entry = {"method": method}
        if "window" in config:
            window = int(config["window"])
            if not 1 <= window <= 101:
                raise ValueError("滤波窗口须在 1 到 101 之间")
            entry["window"] = window
        if "alpha" in config:
            alpha = float(config["alpha"])
            if not 0.01 <= alpha <= 1:
                raise ValueError("指数平滑系数须在 0.01 到 1 之间")
            entry["alpha"] = alpha
        category_methods[category_id] = entry

    incoming_categories = payload.get("signal_categories", {})
    if not isinstance(incoming_categories, dict):
        raise ValueError("signal_categories 必须是对象")
    for param_id, category_id in incoming_categories.items():
        if param_id not in known_params:
            raise ValueError(f"未知测点编号: {param_id}")
        if category_id == "auto":
            signal_categories.pop(param_id, None)
        elif category_id in categories:
            signal_categories[param_id] = category_id
        else:
            raise ValueError(f"未知数据类别: {category_id}")

    incoming_thresholds = payload.get("signal_thresholds", {})
    if not isinstance(incoming_thresholds, dict):
        raise ValueError("signal_thresholds 必须是对象")
    for param_id, value in incoming_thresholds.items():
        if param_id not in known_params or not isinstance(value, dict):
            raise ValueError(f"无效的测点阈值配置: {param_id}")
        if value.get("enabled") is False:
            signal_thresholds[param_id] = {"enabled": False}
            continue
        minimum = value.get("minimum")
        maximum = value.get("maximum")
        try:
            minimum = None if minimum in (None, "") else float(minimum)
            maximum = None if maximum in (None, "") else float(maximum)
        except (TypeError, ValueError):
            raise ValueError(f"{param_id} 的阈值必须为数字")
        if minimum is None and maximum is None:
            signal_thresholds[param_id] = {"enabled": False}
        elif minimum is not None and maximum is not None and minimum >= maximum:
            raise ValueError(f"{param_id} 的下限必须小于上限")
        else:
            signal_thresholds[param_id] = {"minimum": minimum, "maximum": maximum}

    updated = {
        "category_methods": category_methods,
        "signal_categories": signal_categories,
        "signal_thresholds": signal_thresholds,
    }
    db.set_setting(SETTING_KEY, json.dumps(updated, ensure_ascii=False, separators=(",", ":")))
    return updated
