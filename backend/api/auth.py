"""Authentication API — Login, logout, JWT token management."""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash
from backend.database.models import UserModel
import logging

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password required"}), 400

    user = UserModel.get_by_username(data["username"])
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    try:
        if not check_password_hash(user["PasswordHash"], data["password"]):
            return jsonify({"error": "Invalid credentials"}), 401
    except Exception as e:
        logger.error(f"Password hash check error: {e}")
        return jsonify({"error": "Invalid credentials"}), 401

    UserModel.update_last_login(user["UserID"])
    token = create_access_token(identity={
        "user_id":  user["UserID"],
        "username": user["Username"],
        "role":     user["Role"],
        "name":     user["FullName"],
    })
    return jsonify({
        "token":    token,
        "user": {
            "id":       user["UserID"],
            "username": user["Username"],
            "role":     user["Role"],
            "name":     user["FullName"],
        }
    })


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    return jsonify(identity)


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    return jsonify({"message": "Logged out successfully"})
