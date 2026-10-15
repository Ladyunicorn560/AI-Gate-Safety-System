"""
Main Flask Application — AI Gate Safety System
Initializes all components and registers all API blueprints.
"""

import logging
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

load_dotenv()

from backend.config import (
    FLASK_HOST, FLASK_PORT, FLASK_DEBUG, SECRET_KEY,
    JWT_EXPIRES_HOURS, LOG_LEVEL, LOG_FILE
)

# ─── Logging Setup ────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# ─── App Factory ──────────────────────────────────────────────────────────────
def create_app():
    app = Flask(
        __name__,
        static_folder=str(Path(__file__).parent.parent / "frontend"),
        static_url_path="",
    )

    # Config
    app.config["SECRET_KEY"]                      = SECRET_KEY
    app.config["JWT_SECRET_KEY"]                  = SECRET_KEY
    app.config["JWT_ACCESS_TOKEN_EXPIRES"]        = __import__("datetime").timedelta(hours=JWT_EXPIRES_HOURS)
    app.config["MAX_CONTENT_LENGTH"]              = 32 * 1024 * 1024  # 32MB upload limit

    # Extensions
    CORS(app, origins="*")
    jwt = JWTManager(app)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading",
                        logger=False, engineio_logger=False)

    # ── Initialize DB ─────────────────────────────────────────────────────────
    from backend.database.db import initialize_db
    from backend.database.schema import create_database_if_not_exists, run_schema
    try:
        create_database_if_not_exists()
        initialize_db()
        run_schema()
        logger.info("[OK] Database ready.")
    except Exception as e:
        logger.error(f"DB init failed: {e}")

    # ── Initialize AI Models ──────────────────────────────────────────────────
    from backend.ai.face_recognition import face_recognizer
    from backend.ai.ppe_detection import ppe_detector
    from backend.ai.camera_processor import camera_manager
    from backend.database.models import EmployeeModel

    try:
        face_recognizer.initialize()
        enrolled = EmployeeModel.get_all_enrolled_faces()
        face_recognizer.load_known_faces(enrolled)
        logger.info(f"[OK] Face recognizer ready. {len(enrolled)} enrolled employees.")
    except Exception as e:
        logger.error(f"Face recognizer init error: {e}")

    try:
        ppe_detector.initialize()
        logger.info("[OK] PPE detector ready.")
    except Exception as e:
        logger.error(f"PPE detector init error: {e}")

    # ── Initialize Camera Manager ─────────────────────────────────────────────
    camera_manager.socketio = socketio
    camera_manager.initialize()

    # ── Register API Blueprints ───────────────────────────────────────────────
    from backend.api.auth       import auth_bp
    from backend.api.attendance import attendance_bp
    from backend.api.violations import violations_bp
    from backend.api.employees  import employees_bp
    from backend.api.reports    import reports_bp
    from backend.api.dashboard  import dashboard_bp
    from backend.api.cameras    import cameras_bp
    from backend.api.snapshots  import snapshots_bp

    app.register_blueprint(auth_bp,        url_prefix="/api/auth")
    app.register_blueprint(attendance_bp,  url_prefix="/api/attendance")
    app.register_blueprint(violations_bp,  url_prefix="/api/violations")
    app.register_blueprint(employees_bp,   url_prefix="/api/employees")
    app.register_blueprint(reports_bp,     url_prefix="/api/reports")
    app.register_blueprint(dashboard_bp,   url_prefix="/api/dashboard")
    app.register_blueprint(cameras_bp,     url_prefix="/api/cameras")
    app.register_blueprint(snapshots_bp,   url_prefix="/api/snapshots")

    # ── Serve Frontend ────────────────────────────────────────────────────────
    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        if path.startswith("api/"):
            return {"error": f"API endpoint '/{path}' not found"}, 404
        fp = Path(app.static_folder) / path
        if fp.exists():
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, "index.html")

    # ── Health Check ──────────────────────────────────────────────────────────
    @app.route("/api/health")
    def health():
        from backend.database.db import check_health
        db_health = check_health()
        return {
            "status":  "ok",
            "database": db_health,
            "face_model": face_recognizer._initialized,
            "ppe_model":  ppe_detector._initialized,
        }

    # ── SocketIO Events ───────────────────────────────────────────────────────
    @socketio.on("connect")
    def on_connect():
        logger.debug("Client connected to WebSocket.")

    @socketio.on("start_gate_test")
    def on_start_gate_test(data):
        """Frontend can trigger a test stream: {gate_id, source}"""
        gate_id = int(data.get("gate_id", 1))
        source  = data.get("source", 0)
        camera_manager.start_test(gate_id, source)

    @socketio.on("stop_gate")
    def on_stop_gate(data):
        gate_id = int(data.get("gate_id", 1))
        camera_manager.stop_gate(gate_id)

    @socketio.on("reload_faces")
    def on_reload_faces():
        """Reload face embeddings after new enrollment."""
        enrolled = EmployeeModel.get_all_enrolled_faces()
        face_recognizer.load_known_faces(enrolled)
        logger.info(f"Faces reloaded: {len(enrolled)} employees.")

    logger.info(f"[OK] AI Gate Safety System ready on http://{FLASK_HOST}:{FLASK_PORT}")
    return app, socketio


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app, socketio = create_app()
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, allow_unsafe_werkzeug=True)
