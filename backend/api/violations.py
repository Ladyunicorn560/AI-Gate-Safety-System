"""Violations API routes."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.database.models import ViolationModel
from datetime import date
import logging

logger = logging.getLogger(__name__)
violations_bp = Blueprint("violations", __name__)


@violations_bp.route("/recent", methods=["GET"])
@jwt_required()
def recent():
    limit   = request.args.get("limit", 50, type=int)
    gate_id = request.args.get("gate_id", type=int)
    data    = ViolationModel.get_recent(limit=limit, gate_id=gate_id)
    return jsonify({"data": data, "count": len(data)})


@violations_bp.route("/search", methods=["GET"])
@jwt_required()
def search():
    data = ViolationModel.search(
        query          = request.args.get("q"),
        gate_id        = request.args.get("gate_id", type=int),
        violation_type = request.args.get("type"),
        start_date     = request.args.get("start"),
        end_date       = request.args.get("end"),
    )
    return jsonify({"data": data, "count": len(data)})


@violations_bp.route("/stats", methods=["GET"])
@jwt_required()
def stats():
    date_val = request.args.get("date", str(date.today()))
    return jsonify(ViolationModel.get_stats(date_val))


@violations_bp.route("/<int:violation_id>/resolve", methods=["POST"])
@jwt_required()
def resolve(violation_id: int):
    identity = get_jwt_identity()
    ViolationModel.resolve(violation_id, resolved_by=identity.get("user_id"))
    return jsonify({"message": "Violation marked as resolved"})
