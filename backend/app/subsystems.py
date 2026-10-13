"""从共享的公开合成参数配置加载演示测点。"""
import json

from .paths import get_params_path


def _load():
    with open(get_params_path(), encoding="utf-8") as f:
        return json.load(f)


_RAW = _load()

DEVICE = _RAW["device"]
SUBSYSTEMS = _RAW["subsystems"]  # [{code, id, name, params: [...]}, ...]

SUBSYSTEM_BY_ID = {s["id"]: s for s in SUBSYSTEMS}
