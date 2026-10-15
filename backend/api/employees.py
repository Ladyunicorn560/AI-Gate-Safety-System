"""Employees API — CRUD + face enrollment."""

import os
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename
from pathlib import Path
from backend.database.models import EmployeeModel, ContractorModel, GateModel
from backend.config import EMPLOYEE_FACES_DIR
import logging

logger = logging.getLogger(__name__)
employees_bp = Blueprint("employees", __name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@employees_bp.route("/", methods=["GET"])
@jwt_required()
def list_employees():
    q = request.args.get("q")
    if q:
        data = EmployeeModel.search(q)
    else:
        data = EmployeeModel.get_all()
    return jsonify({"data": data, "count": len(data)})


@employees_bp.route("/<int:emp_id>", methods=["GET"])
@jwt_required()
def get_employee(emp_id):
    emp = EmployeeModel.get_by_id(emp_id)
    if not emp:
        return jsonify({"error": "Employee not found"}), 404
    return jsonify(emp)


@employees_bp.route("/", methods=["POST"])
@jwt_required()
def create_employee():
    data = request.get_json()
    if not data or not data.get("emp_code") or not data.get("full_name"):
        return jsonify({"error": "emp_code and full_name are required"}), 400
    emp_id = EmployeeModel.create(data)
    return jsonify({"employee_id": emp_id, "message": "Employee created"}), 201


@employees_bp.route("/<int:emp_id>/enroll-face", methods=["POST"])
@jwt_required()
def enroll_face(emp_id: int):
    """Enroll face from uploaded image file."""
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400

    file = request.files["photo"]
    if not allowed_file(file.filename):
        return jsonify({"error": "Only JPG/PNG images allowed"}), 400

    # Read image from upload
    file_bytes = np.frombuffer(file.read(), np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        return jsonify({"error": "Cannot decode image"}), 400

    from backend.ai.face_recognition import face_recognizer
    if not face_recognizer._initialized:
        return jsonify({"error": "Face recognition model not ready"}), 503

    embedding, photo_path = face_recognizer.enroll_from_frame(img, emp_id)
    if embedding is None:
        return jsonify({"error": "No face detected in image. Please use a clear frontal face photo."}), 400

    EmployeeModel.save_face_embedding(emp_id, embedding, photo_path)

    # Reload embeddings in memory
    from flask_socketio import SocketIO
    enrolled = EmployeeModel.get_all_enrolled_faces()
    face_recognizer.load_known_faces(enrolled)

    return jsonify({"message": "Face enrolled successfully", "photo_path": photo_path})


@employees_bp.route("/<int:emp_id>/photo", methods=["GET"])
@jwt_required()
def get_photo(emp_id: int):
    emp = EmployeeModel.get_by_id(emp_id)
    if not emp or not emp.get("PhotoPath"):
        return jsonify({"error": "No photo found"}), 404
    path = Path(emp["PhotoPath"])
    if not path.exists():
        return jsonify({"error": "Photo file missing"}), 404
    return send_file(str(path), mimetype="image/jpeg")


@employees_bp.route("/<int:emp_id>", methods=["DELETE"])
@jwt_required()
def deactivate_employee(emp_id: int):
    EmployeeModel.deactivate(emp_id)
    return jsonify({"message": "Employee deactivated"})


@employees_bp.route("/contractors", methods=["GET"])
@jwt_required()
def list_contractors():
    return jsonify({"data": ContractorModel.get_all()})


@employees_bp.route("/contractors", methods=["POST"])
@jwt_required()
def create_contractor():
    data = request.get_json()
    cid = ContractorModel.create(data)
    return jsonify({"contractor_id": cid, "message": "Contractor created"}), 201


@employees_bp.route("/gates", methods=["GET"])
@jwt_required()
def list_gates():
    return jsonify({"data": GateModel.get_all()})
