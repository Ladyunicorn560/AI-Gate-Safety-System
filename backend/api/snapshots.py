"""Snapshot serving API — serves violation snapshot images."""

from flask import Blueprint, request, send_file, jsonify, abort
from flask_jwt_extended import jwt_required
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
snapshots_bp = Blueprint("snapshots", __name__)


@snapshots_bp.route("/snapshot", methods=["GET"])
@jwt_required()
def serve_snapshot():
    """Serve a snapshot image by its file path."""
    path = request.args.get("path", "")
    if not path:
        abort(400)
    fp = Path(path)
    if not fp.exists() or not fp.is_file():
        abort(404)
    # Security: only serve files inside violations dir
    try:
        fp.resolve().relative_to(Path("violations").resolve())
    except ValueError:
        abort(403)
    return send_file(str(fp), mimetype="image/jpeg")


@snapshots_bp.route("/violation-snapshot/<int:violation_id>", methods=["GET"])
@jwt_required()
def serve_violation_snapshot(violation_id: int):
    """Serve snapshot by violation ID."""
    from backend.database.models import ViolationModel
    vio = ViolationModel.get_by_id(violation_id)
    if not vio or not vio.get("SnapshotPath"):
        abort(404)
    fp = Path(vio["SnapshotPath"])
    if not fp.exists():
        abort(404)
    return send_file(str(fp), mimetype="image/jpeg")


@snapshots_bp.route("/upload-media/<filename>", methods=["GET"])
def serve_upload_media(filename: str):
    """Serve media files uploaded for model testing."""
    from backend.config import UPLOADS_DIR
    # Prevent directory traversal
    safe_filename = Path(filename).name
    fp = UPLOADS_DIR / safe_filename
    if not fp.exists() or not fp.is_file():
        abort(404)
    ext = fp.suffix.lower()
    mimetypes = {
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
        ".webp": "image/webp",
        ".mp4":  "video/mp4",
        ".webm": "video/webm",
        ".avi":  "video/x-msvideo",
        ".mov":  "video/quicktime",
    }
    return send_file(str(fp), mimetype=mimetypes.get(ext, "application/octet-stream"))

