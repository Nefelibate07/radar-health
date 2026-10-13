"""Live hierarchical fault diagnosis API, independent of health score APIs."""
from flask import Blueprint, jsonify

from ..fault_diagnosis import get_fault_diagnosis

bp = Blueprint("fault_diagnosis", __name__)


@bp.get("/api/fault-diagnosis")
def get_fault_diagnosis_snapshot():
    return jsonify(get_fault_diagnosis())
