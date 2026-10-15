"""Attendance API routes."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from backend.database.models import AttendanceModel
from datetime import date
import logging

logger = logging.getLogger(__name__)
attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/today", methods=["GET"])
@jwt_required()
def today():
    gate_id = request.args.get("gate_id", type=int)
    contractor_id = request.args.get("contractor_id", type=int)
    data = AttendanceModel.get_today(gate_id=gate_id, contractor_id=contractor_id)
    return jsonify({"data": data, "count": len(data)})


@attendance_bp.route("/summary", methods=["GET"])
@jwt_required()
def summary():
    date_val = request.args.get("date", str(date.today()))
    return jsonify(AttendanceModel.get_summary(date_val))


@attendance_bp.route("/range", methods=["GET"])
@jwt_required()
def date_range():
    start = request.args.get("start", str(date.today()))
    end   = request.args.get("end",   str(date.today()))
    gate_id = request.args.get("gate_id", type=int)
    contractor_id = request.args.get("contractor_id", type=int)
    employee_id   = request.args.get("employee_id", type=int)
    data = AttendanceModel.get_by_date_range(start, end, gate_id, contractor_id, employee_id)
    return jsonify({"data": data, "count": len(data)})


@attendance_bp.route("/manual-exit/<int:employee_id>", methods=["POST"])
@jwt_required()
def manual_exit(employee_id: int):
    AttendanceModel.log_exit(employee_id)
    return jsonify({"message": "Exit time recorded"})
