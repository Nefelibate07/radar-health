"""从公开合成配置生成前端测点，永远不导入私有工程。"""
import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
SUBSYSTEMS = json.loads((ROOT / "config/params.json").read_text(encoding="utf-8"))["subsystems"]

def _demo_signal(p, idx):
    """由参数生成一个 signal: {name,value,unit,threshold,status,dtype,appendix_no,review}"""
    unit = p["unit"] or ""
    dtype = p["dtype"]
    if dtype == "enum":
        # 状态量:正常码=1,阈值取"告警"码;演示值给正常
        value = 1
        threshold = 2
    elif dtype == "bool":
        value, threshold = 1, 1
    elif dtype == "int":
        value, threshold = 3, 10
    elif dtype == "datetime":
        value, threshold = 0, 0
    else:  # float
        if p["range"]:
            lo, hi = p["range"]
            value = round(lo + (hi - lo) * 0.4, 3)
            threshold = hi
        else:
            # 无范围:用精度量级给个温和默认
            base = {"°": 30.0, "°/s": 0.3, "A": 5.0, "V": 28.0, "mV": 50.0,
                    "℃": 45.0, "mm/s": 2.0, "μm": 200.0, "dB": 3.0, "dBm": -40.0,
                    "%": 30.0, "Hz": 50.0, "MPa": 0.4, "MPa/h": 0.01, "次": 3.0}.get(unit, 1.0)
            value = base
            threshold = base * 2 if base > 0 else base + 10
    return {"name": p["name"], "value": value, "unit": unit, "threshold": threshold,
            "status": "ok", "dtype": dtype, "appendix_no": p["appendix_no"],
            "review": p["review"]}


def build_frontend(root):
    blocks = []
    for s in SUBSYSTEMS:
        signals = [_demo_signal(p, i) for i, p in enumerate(s["params"])]
        # 主参数:优先取第一个 float 参数,否则第一个参数;空子系统(占位)无主参数
        if signals:
            main = next((sg for sg in signals if sg["dtype"] == "float"), signals[0])
            main_param = {"label": main["name"], "value": main["value"],
                          "unit": main["unit"], "threshold": main["threshold"]}
        else:
            main_param = None
        blocks.append({"id": s["id"], "code": s["code"], "name": s["name"],
                       "health": 96, "status": "ok",
                       "paramCount": len(s["params"]),
                       "mainParam": main_param, "signals": signals})
    header = (
        "// ⚠️ 本文件由 config/build_params.py 自动生成,请勿手改。\n"
        "// 数据源: config/params.json (公开合成演示配置)。\n"
        "// 演示值为占位,合成演示值由后端推送更新。\n\n"
        "export const SUBSYSTEMS = "
    )
    body = json.dumps(blocks, ensure_ascii=False, indent=2)
    helpers = """

export function getSubsystemById(id) {
  return SUBSYSTEMS.find((s) => s.id === id) || null
}

export function getSubsystemStatusClass(status) {
  return { ok: 'status-ok', warn: 'status-warn', danger: 'status-danger' }[status] || 'status-ok'
}

export function getSubsystemStatusText(status) {
  return { ok: '健康', warn: '关注', danger: '危险' }[status] || '未知'
}

export function evalSignalStatus(value, threshold, higherIsBetter = false) {
  if (higherIsBetter) {
    if (value >= threshold * 1.05) return 'ok'
    if (value >= threshold * 0.9) return 'warn'
    return 'danger'
  }
  if (value <= threshold * 0.95) return 'ok'
  if (value <= threshold * 1.1) return 'warn'
  return 'danger'
}
"""
    out = os.path.join(root, "frontend", "src", "config", "subsystems.generated.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write(header + body + "\n" + helpers)


if __name__ == "__main__":
    build_frontend(str(ROOT))
    print("生成完成：公开合成演示配置")
