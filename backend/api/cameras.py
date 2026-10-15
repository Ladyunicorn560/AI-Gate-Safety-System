"""Camera management API — start/stop gates, configure RTSP URLs."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from backend.ai.camera_processor import camera_manager
from backend.database.models import GateModel
import logging

logger = logging.getLogger(__name__)
cameras_bp = Blueprint("cameras", __name__)


@cameras_bp.route("/status", methods=["GET"])
@jwt_required()
def status():
    return jsonify({"data": camera_manager.get_all_stats()})


@cameras_bp.route("/start/<int:gate_id>", methods=["POST"])
@jwt_required()
def start(gate_id: int):
    data   = request.get_json() or {}
    source = data.get("source")  # RTSP URL, webcam index, or video path
    camera_manager.start_gate(gate_id, source)
    return jsonify({"message": f"Gate {gate_id} camera starting"})


@cameras_bp.route("/stop/<int:gate_id>", methods=["POST"])
@jwt_required()
def stop(gate_id: int):
    camera_manager.stop_gate(gate_id)
    return jsonify({"message": f"Gate {gate_id} camera stopped"})


@cameras_bp.route("/start-all", methods=["POST"])
@jwt_required()
def start_all():
    camera_manager.start_all()
    return jsonify({"message": "All gate cameras starting"})


@cameras_bp.route("/stop-all", methods=["POST"])
@jwt_required()
def stop_all():
    camera_manager.stop_all()
    return jsonify({"message": "All cameras stopped"})


@cameras_bp.route("/configure/<int:gate_id>", methods=["POST"])
@jwt_required()
def configure(gate_id: int):
    data = request.get_json()
    rtsp = data.get("rtsp_url", "")
    GateModel.update_rtsp(gate_id, rtsp)
    # Update live processor too
    if gate_id in camera_manager.processors:
        camera_manager.processors[gate_id].rtsp_url = rtsp
    return jsonify({"message": f"Gate {gate_id} RTSP configured"})


@cameras_bp.route("/test-image/<int:gate_id>", methods=["POST"])
@jwt_required()
def test_image(gate_id: int):
    """Test PPE detection on an uploaded image."""
    import cv2, numpy as np
    from backend.ai.face_recognition import face_recognizer
    from backend.ai.ppe_detection import ppe_detector

    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file  = request.files["image"]
    fbytes = np.frombuffer(file.read(), np.uint8)
    img   = cv2.imdecode(fbytes, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Cannot decode image"}), 400

    ppe_results  = ppe_detector.detect(img)
    face_results = face_recognizer.process_frame(img) if face_recognizer._initialized else []
    violations   = ppe_detector.get_violations(ppe_results)

    return jsonify({
        "ppe_detections": ppe_results,
        "face_results":   [{k: v for k, v in r.items() if k != "employee" or v is None
                           } for r in face_results],
        "violations":     violations,
        "violation_count": len(violations),
    })
