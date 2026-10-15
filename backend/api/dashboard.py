"""Dashboard API — aggregated stats for the live dashboard & model playground upload."""

import base64
import cv2
import logging
import numpy as np
import time
import uuid
from datetime import date
from pathlib import Path
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from backend.ai.camera_processor import camera_manager
from backend.ai.face_recognition import face_recognizer
from backend.ai.ppe_detection import ppe_detector
from backend.config import UPLOADS_DIR, PPE_IMAGE_SIZE_UPLOAD
from backend.database.models import AttendanceModel, GateModel, ViolationModel

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/stats", methods=["GET"])
def stats():
    """Main dashboard KPIs."""
    today = str(date.today())
    att_summary = AttendanceModel.get_summary(today)
    vio_stats   = ViolationModel.get_stats(today)
    camera_stats = camera_manager.get_all_stats()

    return jsonify({
        "attendance":     att_summary,
        "violations":     vio_stats,
        "cameras":        camera_stats,
        "date":           today,
    })


@dashboard_bp.route("/gates", methods=["GET"])
def gates():
    gates = GateModel.get_all()
    camera_stats = {s["gate_id"]: s for s in camera_manager.get_all_stats()}
    for gate in gates:
        gid = gate["GateID"]
        cam = camera_stats.get(gid, {})
        gate["camera_status"]     = cam.get("status", "stopped")
        gate["persons_detected"]  = cam.get("persons_detected", 0)
        gate["violations_today"]  = cam.get("violations_today", 0)
    return jsonify({"data": gates})


@dashboard_bp.route("/recent-activity", methods=["GET"])
def recent_activity():
    attendance  = AttendanceModel.get_today()[:10]
    violations  = ViolationModel.get_recent(limit=10)
    return jsonify({
        "attendance":  attendance,
        "violations":  violations,
    })


@dashboard_bp.route("/test-upload", methods=["POST"])
def test_upload():
    """
    Model Playground API:
    Allows uploading an Image or Video file to test YOLOv8 PPE detection & InsightFace models.
    Returns annotated output + detection metadata.
    """
    file = request.files.get("file") or request.files.get("media")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    ext = Path(file.filename).suffix.lower()
    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    if ext not in image_exts and ext not in video_exts:
        return jsonify({"error": f"Unsupported file format '{ext}'. Allowed formats: JPG, PNG, WEBP, MP4, AVI, MOV, WEBM"}), 400

    # Ensure models initialized
    if not ppe_detector._initialized:
        ppe_detector.initialize()
    if not face_recognizer._initialized:
        face_recognizer.initialize()

    # ── Handle Image Upload ──────────────────────────────────────────────────
    if ext in image_exts:
        try:
            file_bytes = file.read()
            nparr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if img is None:
                return jsonify({"error": "Failed to decode image file."}), 400

            # Run AI Inference
            face_results = face_recognizer.process_frame(img)
            ppe_detections = ppe_detector.detect(img, imgsz=PPE_IMAGE_SIZE_UPLOAD)

            # Draw Annotations
            annotated = face_recognizer.draw_results(img.copy(), face_results)
            annotated = ppe_detector.draw_detections(annotated, ppe_detections)
            annotated = ppe_detector.overlay_stats(annotated, ppe_detections)

            # Encode annotated image as Base64 JPEG
            _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
            b64_str = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("utf-8")

            # Also encode original image for side-by-side comparison
            _, orig_buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            orig_b64 = "data:image/jpeg;base64," + base64.b64encode(orig_buf.tobytes()).decode("utf-8")

            # Extract Summary Data
            violations = ppe_detector.get_violations(ppe_detections)
            persons = [d for d in ppe_detections if d["class_name"].lower() == "person"]
            matched_emps = [r["employee"]["full_name"] for r in face_results if r.get("matched")]

            return jsonify({
                "status": "success",
                "media_type": "image",
                "original_image": orig_b64,
                "annotated_image": b64_str,
                "detections": ppe_detections,
                "face_matches": face_results,
                "summary": {
                    "persons": len(persons),
                    "violations_count": len(violations),
                    "violations": [v["class_name"] for v in violations],
                    "compliance_pass": len(violations) == 0,
                    "matched_employees": matched_emps,
                    "total_objects": len(ppe_detections)
                }
            })
        except Exception as e:
            logger.error(f"Test image processing failed: {e}", exc_info=True)
            return jsonify({"error": f"Image processing error: {str(e)}"}), 500

    # ── Handle Video Upload ──────────────────────────────────────────────────
    if ext in video_exts:
        try:
            filename = f"test_{int(time.time())}_{uuid.uuid4().hex[:6]}{ext}"
            save_path = UPLOADS_DIR / filename
            file.save(str(save_path))

            cap = cv2.VideoCapture(str(save_path))
            if not cap.isOpened():
                return jsonify({"error": "Failed to open video file."}), 400

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            # Limit total frames processed to max 150 frames for fast web response
            max_frames = 150
            step = max(1, total_frames // max_frames) if total_frames > max_frames else 1

            # Output video path
            out_filename = f"annotated_{filename}"
            out_path = UPLOADS_DIR / out_filename
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_writer = cv2.VideoWriter(str(out_path), fourcc, min(fps, 15), (width, height))

            all_violations = []
            all_matched = set()
            max_persons = 0
            processed_count = 0
            keyframes = []
            timeline = []

            frame_idx = 0
            while cap.isOpened() and processed_count < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % step == 0:
                    processed_count += 1
                    t_sec = round(frame_idx / fps, 1) if fps else 0

                    face_results = face_recognizer.process_frame(frame)
                    ppe_detections = ppe_detector.detect(frame)

                    annotated = face_recognizer.draw_results(frame.copy(), face_results)
                    annotated = ppe_detector.draw_detections(annotated, ppe_detections)
                    annotated = ppe_detector.overlay_stats(annotated, ppe_detections)

                    if out_writer.isOpened():
                        out_writer.write(annotated)

                    violations = ppe_detector.get_violations(ppe_detections)
                    persons = [d for d in ppe_detections if d["class_name"].lower() == "person"]

                    for r in face_results:
                        if r.get("matched"):
                            all_matched.add(r["employee"]["full_name"])

                    all_violations.extend(violations)
                    if len(persons) > max_persons:
                        max_persons = len(persons)

                    timeline.append({
                        "frame": frame_idx,
                        "time_sec": t_sec,
                        "persons": len(persons),
                        "violations": len(violations),
                        "violation_types": [v["class_name"] for v in violations]
                    })

                    # Store keyframes (max 3 keyframes with detections/violations)
                    if len(keyframes) < 3 and (violations or len(persons) > 0 or processed_count == 1):
                        _, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        keyframes.append({
                            "timestamp": f"{t_sec}s",
                            "violations": len(violations),
                            "persons": len(persons),
                            "image": "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("utf-8")
                        })

                frame_idx += 1

            cap.release()
            out_writer.release()

            return jsonify({
                "status": "success",
                "media_type": "video",
                "video_url": f"/api/snapshots/upload-media/{out_filename}",
                "raw_video_url": f"/api/snapshots/upload-media/{filename}",
                "keyframes": keyframes,
                "video_info": {
                    "duration_sec": round(total_frames / fps, 1) if fps else 0,
                    "total_frames": total_frames,
                    "processed_frames": processed_count
                },
                "summary": {
                    "peak_persons": max_persons,
                    "total_violations_found": len(all_violations),
                    "unique_violations": list(set([v["class_name"] for v in all_violations])),
                    "compliance_pass": len(all_violations) == 0,
                    "matched_employees": list(all_matched),
                    "timeline": timeline[:20]
                }
            })
        except Exception as e:
            logger.error(f"Test video processing failed: {e}", exc_info=True)
            return jsonify({"error": f"Video processing error: {str(e)}"}), 500
