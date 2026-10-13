"""Configuration-driven signal -> component -> subsystem -> system diagnosis."""
import json

from .data_processing import get_processing_snapshot
from .paths import get_config_dir
from .scenario import SCENARIO_MODES
from .subsystems import SUBSYSTEMS


def _catalog():
    with open(get_config_dir() / "fault_diagnosis.json", encoding="utf-8") as source:
        return json.load(source)


def _status(signals):
    if not signals:
        return "无数据"
    levels = {item.get("severity") for item in signals}
    if "fault" in levels:
        return "故障"
    if "unknown" in levels:
        return "待完善"
    return "正常"


def _contains(text, words):
    return any(word in text for word in words)


def _signal_fault_class(signal, is_motor):
    if signal.get("severity") != "fault":
        return None
    name = str(signal.get("name") or "")
    reason = str(signal.get("reason") or "")
    combined = f"{name} {reason}"
    status = str(signal.get("status") or "")

    if is_motor:
        if _contains(combined, ("去电", "断开", "掉电")) or ("加电" in name and status == "状态告警"):
            return "电机掉电"
        if "电流" in name and status == "越限":
            return "过流"
        if "电压" in name and status == "越限":
            return "电压异常"
        if "制动器" in name:
            return "制动器异常"
        if "减速机" in name:
            return "减速机异常"
        if "轴承" in name:
            return "轴承异常（待细分）"
        if _contains(name, ("电机状态", "转速", "转子")):
            return "电机卡顿"

    if status == "越限":
        if _contains(name, ("温度", "湿度", "空调", "冷却")):
            return "环境参数越限"
        if _contains(name, ("电流",)):
            return "电流越限"
        if _contains(name, ("电压",)):
            return "电压越限"
        if _contains(name, ("角度", "方位", "俯仰", "编码")):
            return "测量参数越限"
        return "测点越限"
    if _contains(combined, ("通信", "跟踪", "接收", "失锁", "链路")):
        return "通信与跟踪告警"
    if _contains(combined, ("供电", "电源", "掉电")):
        return "供电状态告警"
    return "设备状态告警"


def _system_fault_class(subsystem, component, fault):
    text = " ".join((
        str(subsystem.get("name") or ""),
        str(component.get("name") or ""),
        str(fault.get("fault_class") or ""),
        str(fault.get("signal_name") or ""),
    ))
    if _contains(text, ("掉电", "供电", "电源", "过流", "电压异常")):
        return "供电故障"
    if _contains(text, ("电机", "驱动", "转速", "转子", "轴承", "减速机", "制动器", "传动")):
        return "驱动与传动故障"
    if _contains(text, ("通信", "跟踪", "接收", "失锁", "链路")):
        return "通信与跟踪故障"
    if _contains(text, ("温度", "湿度", "空调", "冷却", "环境")):
        return "环境控制故障"
    if _contains(text, ("角度", "方位", "俯仰", "编码", "测量")):
        return "测量故障"
    if _contains(text, ("越限", "测点")):
        return "参数越限"
    return "设备状态告警"


def _fallback_component(signal, is_motor, config):
    """Assign newly added parameter IDs when the explicit config has no entry."""
    name = str(signal.get("name") or "")
    catalog = config["motor_components"] if is_motor else config["generic_components"]
    if is_motor:
        if _contains(name, ("电流", "电压", "加电", "供电", "电源")):
            component_id = "power"
        elif _contains(name, ("轴承", "减速机", "制动器", "齿轮")):
            component_id = "bearing"
        else:
            component_id = "rotor"
    else:
        component_id = "other"
        for component in catalog:
            if _contains(name, component.get("keywords", [])):
                component_id = component["id"]
                break
    definition = next((item for item in catalog if item["id"] == component_id), catalog[-1])
    return component_id, {
        "id": component_id,
        "name": definition["name"],
        "signal_ids": [],
        "fault_classes": definition.get("fault_classes", config.get("generic_fault_classes", [])),
    }


def _component_templates(subsystem_id, subsystem, is_motor, config):
    configured = config.get("components_by_subsystem", {}).get(subsystem_id)
    if subsystem_id in config.get("components_by_subsystem", {}):
        return [dict(item) for item in configured]
    rules = config["motor_components"] if is_motor else config["generic_components"]
    return [
        {
            "id": item["id"],
            "name": f"{subsystem['name']} · {item['name']}",
            "signal_ids": [],
            "fault_classes": item.get("fault_classes", config.get("generic_fault_classes", [])),
        }
        for item in rules
        if is_motor or item["id"] == "other"
    ]


def get_fault_diagnosis():
    processed = get_processing_snapshot()["data"]
    config = _catalog()
    motor_ids = set(config.get("motor_subsystem_ids", []))
    component_maps = config.get("signal_component_map", {})
    definitions = {item["id"]: item for item in SUBSYSTEMS}
    grouped = {item["id"]: [] for item in SUBSYSTEMS}
    for signal in processed.get("signals", []):
        subsystem_id = signal.get("subsystem_id")
        if subsystem_id in grouped:
            grouped[subsystem_id].append(signal)

    subsystem_results = []
    system_findings = []
    system_incidents = []
    for subsystem_id, subsystem in definitions.items():
        is_motor = subsystem_id in motor_ids
        templates = _component_templates(subsystem_id, subsystem, is_motor, config)
        component_groups = {item["id"]: {"definition": item, "signals": []} for item in templates}
        explicit_map = component_maps.get(subsystem_id, {})

        for signal in grouped[subsystem_id]:
            component_id = explicit_map.get(signal["id"])
            if component_id not in component_groups:
                component_id, definition = _fallback_component(signal, is_motor, config)
                component_groups.setdefault(component_id, {"definition": definition, "signals": []})
            component_groups[component_id]["signals"].append(signal)

        components = []
        for component_id, group in component_groups.items():
            component_signals = group["signals"]
            definition = group["definition"]
            faults = []
            for signal in component_signals:
                fault_class = _signal_fault_class(signal, is_motor)
                signal["fault_class"] = fault_class
                if fault_class:
                    fault = {
                        "signal_id": signal["id"],
                        "signal_name": signal["name"],
                        "fault_class": fault_class,
                        "reason": signal.get("reason"),
                    }
                    faults.append(fault)
                    system_findings.append({
                        **fault,
                        "subsystem_id": subsystem_id,
                        "subsystem": subsystem["name"],
                        "component_id": f"{subsystem_id}:{component_id}",
                        "component": definition["name"],
                    })

            status = _status(component_signals)
            component = {
                "id": f"{subsystem_id}:{component_id}",
                "name": definition["name"],
                "status": status,
                "fault_class": faults[0]["fault_class"] if faults else None,
                "faults": faults,
                "candidate_fault_classes": definition.get("fault_classes", config.get("generic_fault_classes", [])),
                "data_scope": definition.get("data_scope"),
                "evaluated_signal_count": sum(item.get("severity") in {"normal", "fault"} for item in component_signals),
                "signal_count": len(component_signals),
                "signals": component_signals,
            }
            components.append(component)
            for incident in faults:
                system_incidents.append({
                    "subsystem_id": subsystem_id,
                    "subsystem": subsystem["name"],
                    "component_id": component["id"],
                    "component": component["name"],
                    "fault_class": _system_fault_class(subsystem, component, incident),
                    "signal_name": incident["signal_name"],
                    "reason": incident.get("reason"),
                })

        subsystem_signals = grouped[subsystem_id]
        status = _status(subsystem_signals)
        subsystem_faults = [fault for component in components for fault in component["faults"]]
        subsystem_class = subsystem_faults[0]["fault_class"] if subsystem_faults else None
        if is_motor and subsystem_faults:
            fault_classes = {item["fault_class"] for item in subsystem_faults}
            priority = ("电机掉电", "过流", "电压异常", "电机卡顿", "减速机异常", "轴承异常（待细分）", "制动器异常")
            subsystem_class = next((name for name in priority if name in fault_classes), subsystem_class)
        subsystem_results.append({
            "id": subsystem_id,
            "name": subsystem["name"],
            "status": status,
            "fault_class": subsystem_class,
            "candidate_fault_scope": "subsystem",
            "candidate_fault_classes": config.get("subsystem_fault_classes", {}).get(
                subsystem_id,
                config.get("motor_fault_classes", []) if is_motor else config.get("system_fault_classes", []),
            ),
            "components": components,
            "signal_count": len(subsystem_signals),
            "evaluated_signal_count": sum(item.get("severity") in {"normal", "fault"} for item in subsystem_signals),
        })

    fault_subsystems = [item for item in subsystem_results if item["status"] == "故障"]
    incomplete_subsystems = [item for item in subsystem_results if item["status"] == "待完善"]
    system_status = "故障" if fault_subsystems else ("待完善" if incomplete_subsystems else "正常")
    class_priority = {name: index for index, name in enumerate(config.get("system_fault_classes", []))}
    scenario_mode = processed.get("mode") or "normal"
    scenario_affected = set(SCENARIO_MODES.get(scenario_mode, {}).get("affected", set()))
    primary_incident = min(
        system_incidents,
        key=lambda item: (
            0 if scenario_mode != "normal" and item["subsystem_id"] in scenario_affected else 1,
            class_priority.get(item["fault_class"], 100),
            item["subsystem"],
        ),
        default=None,
    )
    if primary_incident:
        system_class = primary_incident["fault_class"]
    elif incomplete_subsystems:
        system_class = "待配置测点阈值"
    else:
        system_class = None

    data = {
        "timestamp": processed.get("timestamp"),
        "sequence": processed.get("sequence"),
        "source_type": processed.get("source_type"),
        "mode": processed.get("mode"),
        "mode_label": processed.get("mode_label"),
        "health_score": None,
        "system": {
            "status": system_status,
            "fault_class": system_class,
            "primary_subsystem_id": primary_incident["subsystem_id"] if primary_incident else None,
            "primary_subsystem": primary_incident["subsystem"] if primary_incident else None,
            "primary_component": primary_incident["component"] if primary_incident else None,
            "fault_count": len(system_findings),
            "faults": system_findings,
            "candidate_fault_classes": config.get("system_fault_classes", []),
        },
        "summary": {
            "subsystem_count": len(subsystem_results),
            "component_count": sum(len(item["components"]) for item in subsystem_results),
            "fault_subsystem_count": len(fault_subsystems),
            "incomplete_subsystem_count": len(incomplete_subsystems),
            "fault_component_count": sum(1 for subsystem in subsystem_results for component in subsystem["components"] if component["status"] == "故障"),
            "fault_signal_count": sum(1 for item in processed.get("signals", []) if item.get("severity") == "fault"),
            "unconfigured_numeric_count": sum(1 for item in processed.get("signals", []) if item.get("status") == "待配置阈值"),
            "signal_count": len(processed.get("signals", [])),
            "categorized_subsystem_count": sum(bool(item["candidate_fault_classes"]) for item in subsystem_results),
            "categorized_component_count": sum(bool(component["candidate_fault_classes"]) for item in subsystem_results for component in item["components"]),
        },
        "subsystems": subsystem_results,
        "classification_mode": "rule_based_hierarchical",
        "classification_note": "故障诊断独立于健康度评估。页面列出的子系统级与功能部件级分类是规则诊断范围，不表示每类都有已接入测点或已被实时证实；实时结论仍由已接入信号、阈值和枚举判据决定。无参数子系统会显示待接入部件。机械故障细分类仍需真实标注数据校准。",
    }
    return {"ok": True, "data": data}
