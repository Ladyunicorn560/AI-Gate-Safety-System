"""
Multi-Gate Camera Processor
Runs one thread per gate camera. Processes frames through:
  1. Face Recognition → attendance logging
  2. PPE Detection → violation logging + snapshots + alerts
Broadcasts results via SocketIO for live dashboard.
"""

import cv2
import threading
import logging
import time
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from backend.config import (
    GATES, CAMERA_FPS, CAMERA_RECONNECT_DELAY,
    ATTENDANCE_COOLDOWN_MINUTES, VIOLATIONS_DIR
)
from backend.ai.face_recognition import face_recognizer
from backend.ai.ppe_detection import ppe_detector
from backend.utils.snapshot import save_violation_snapshot
from backend.utils.alert_manager import alert_manager

logger = logging.getLogger(__name__)


class GateCameraProcessor:
    """
    Processes a single gate camera stream.
    Runs face recognition + PPE detection on every N-th frame.
    """

    def __init__(self, gate_id: int, gate_info: dict, socketio=None):
        self.gate_id    = gate_id
        self.gate_name  = gate_info["name"]
        self.rtsp_url   = gate_info.get("rtsp_url", "")
        self.socketio   = socketio

        self._thread    = None
        self._running   = False
        self._cap       = None

        # Cooldown tracking to avoid duplicate attendance logs
        # {employee_id: last_logged_datetime}
        self._attendance_cooldown: dict = {}

        # Stats for dashboard
        self.stats = {
            "gate_id":    gate_id,
            "gate_name":  self.gate_name,
            "status":     "stopped",
            "fps":        0,
            "persons_detected": 0,
            "violations_today": 0,
            "last_frame_time":  None,
        }

    def start(self, source=None):
        """
        Start processing. source can be:
          - None → use RTSP from config
          - int  → webcam index (e.g. 0)
          - str  → video file path or RTSP URL
        """
        if self._running:
            logger.warning(f"Gate {self.gate_id} already running.")
            return

        self.rtsp_url = source if source is not None else self.rtsp_url
        self._running = True
        self._thread = threading.Thread(
            target=self._process_loop,
            name=f"Gate-{self.gate_id}-Thread",
            daemon=True
        )
        self._thread.start()
        logger.info(f"✅ Gate {self.gate_id} ({self.gate_name}) camera started.")

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()
        self.stats["status"] = "stopped"
        logger.info(f"Gate {self.gate_id} camera stopped.")

    def _open_capture(self):
        """Open video capture with retry."""
        if self._cap:
            self._cap.release()
        if isinstance(self.rtsp_url, int) or (isinstance(self.rtsp_url, str) and self.rtsp_url.isdigit()):
            self._cap = cv2.VideoCapture(int(self.rtsp_url))
        else:
            self._cap = cv2.VideoCapture(self.rtsp_url)

        if self._cap.isOpened():
            self.stats["status"] = "running"
            logger.info(f"Gate {self.gate_id}: Camera opened → {self.rtsp_url}")
        else:
            self.stats["status"] = "error"
            logger.error(f"Gate {self.gate_id}: Cannot open → {self.rtsp_url}")
        return self._cap.isOpened()

    def _process_loop(self):
        """Main processing loop."""
        frame_interval = 1.0 / CAMERA_FPS
        frame_count = 0

        while self._running:
            if not self._open_capture():
                time.sleep(CAMERA_RECONNECT_DELAY)
                continue

            while self._running and self._cap.isOpened():
                t_start = time.time()
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning(f"Gate {self.gate_id}: Frame read failed — reconnecting.")
                    break

                frame_count += 1
                self.stats["last_frame_time"] = datetime.now().isoformat()

                try:
                    annotated_frame = self._process_frame(frame, frame_count)
                    self._broadcast_frame(annotated_frame)
                except Exception as e:
                    logger.error(f"Gate {self.gate_id} frame error: {e}")

                # Rate limiting
                elapsed = time.time() - t_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

            self._cap.release()
            if self._running:
                time.sleep(CAMERA_RECONNECT_DELAY)

    def _process_frame(self, frame: np.ndarray, frame_count: int) -> np.ndarray:
        """Run face recognition and PPE detection on a frame."""
        # ── Face Recognition ──────────────────────────────────────────────────
        face_results = face_recognizer.process_frame(frame)
        for res in face_results:
            if res["matched"]:
                emp = res["employee"]
                self._handle_attendance(emp, res["det_score"])

        # ── PPE Detection ─────────────────────────────────────────────────────
        ppe_detections = ppe_detector.detect(frame)
        violations = ppe_detector.get_violations(ppe_detections)

        for violation in violations:
            self._handle_violation(frame, violation, face_results)

        # ── Annotate Frame ────────────────────────────────────────────────────
        annotated = face_recognizer.draw_results(frame.copy(), face_results)
        annotated = ppe_detector.draw_detections(annotated, ppe_detections)
        annotated = ppe_detector.overlay_stats(annotated, ppe_detections)

        # Gate info overlay
        cv2.putText(annotated, f"{self.gate_name} | {datetime.now().strftime('%H:%M:%S')}",
                    (10, annotated.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Update stats
        persons = [d for d in ppe_detections if d["class_name"].lower() == "person"]
        self.stats["persons_detected"] = len(persons)

        return annotated

    def _handle_attendance(self, employee: dict, confidence: float):
        """Log attendance with cooldown check."""
        emp_id = employee["employee_id"]
        now = datetime.now()
        last = self._attendance_cooldown.get(emp_id)

        if last and (now - last) < timedelta(minutes=ATTENDANCE_COOLDOWN_MINUTES):
            return  # Within cooldown

        self._attendance_cooldown[emp_id] = now

        # Import here to avoid circular imports
        from backend.database.models import AttendanceModel
        try:
            AttendanceModel.log_entry(emp_id, self.gate_id, confidence)
            logger.info(f"✅ Attendance: {employee['full_name']} @ {self.gate_name}")

            if self.socketio:
                self.socketio.emit("attendance_event", {
                    "gate_id":    self.gate_id,
                    "gate_name":  self.gate_name,
                    "emp_code":   employee["emp_code"],
                    "full_name":  employee["full_name"],
                    "confidence": confidence,
                    "timestamp":  now.isoformat(),
                })
        except Exception as e:
            logger.error(f"Attendance log error: {e}")

    def _handle_violation(self, frame: np.ndarray, violation: dict, face_results: list):
        """Log PPE violation: save snapshot, log to DB, trigger alert."""
        from backend.database.models import ViolationModel

        # Try to identify who the violation belongs to
        employee_id = None
        if face_results and face_results[0]["matched"]:
            employee_id = face_results[0]["employee"]["employee_id"]

        # Save snapshot
        snapshot_path = save_violation_snapshot(
            frame, self.gate_id, violation["class_name"]
        )

        try:
            vid = ViolationModel.log(
                gate_id=self.gate_id,
                violation_type=violation["class_name"],
                snapshot_path=snapshot_path,
                employee_id=employee_id,
                confidence=violation["confidence"],
            )
            self.stats["violations_today"] = self.stats.get("violations_today", 0) + 1

            # Trigger alert
            alert_manager.trigger(self.gate_id, self.gate_name, violation["class_name"], vid)

            if self.socketio:
                self.socketio.emit("violation_event", {
                    "gate_id":       self.gate_id,
                    "gate_name":     self.gate_name,
                    "violation_id":  vid,
                    "violation_type": violation["class_name"],
                    "snapshot_path": snapshot_path,
                    "timestamp":     datetime.now().isoformat(),
                    "employee_id":   employee_id,
                })
            logger.warning(f"🚨 Violation: {violation['class_name']} @ {self.gate_name}")
        except Exception as e:
            logger.error(f"Violation log error: {e}")

    def _broadcast_frame(self, frame: np.ndarray):
        """Encode frame as JPEG and broadcast to dashboard via SocketIO."""
        if not self.socketio:
            return
        try:
            # Resize for bandwidth
            small = cv2.resize(frame, (640, 360))
            _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
            import base64
            frame_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
            self.socketio.emit(f"frame_gate_{self.gate_id}", {
                "gate_id": self.gate_id,
                "frame":   frame_b64,
                "stats":   self.stats,
            })
        except Exception as e:
            logger.debug(f"Frame broadcast error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
class CameraManager:
    """Manages all gate camera processors."""

    def __init__(self, socketio=None):
        self.socketio   = socketio
        self.processors: dict[int, GateCameraProcessor] = {}

    def initialize(self):
        """Create a processor for each configured gate."""
        for gate_id, gate_info in GATES.items():
            self.processors[gate_id] = GateCameraProcessor(
                gate_id, gate_info, self.socketio
            )
        logger.info(f"✅ CameraManager initialized for {len(self.processors)} gates.")

    def start_gate(self, gate_id: int, source=None):
        """Start a specific gate's camera."""
        if gate_id in self.processors:
            self.processors[gate_id].start(source)

    def start_all(self):
        """Start all gates with configured RTSP URLs."""
        for gate_id, proc in self.processors.items():
            if proc.rtsp_url:
                proc.start()
            else:
                logger.info(f"Gate {gate_id}: No RTSP URL configured — skipped.")

    def stop_gate(self, gate_id: int):
        if gate_id in self.processors:
            self.processors[gate_id].stop()

    def stop_all(self):
        for proc in self.processors.values():
            proc.stop()

    def get_all_stats(self) -> list:
        return [proc.stats for proc in self.processors.values()]

    def start_test(self, gate_id: int, source):
        """Start a gate from a test video or image for demo/testing."""
        if gate_id not in self.processors:
            self.processors[gate_id] = GateCameraProcessor(
                gate_id, GATES.get(gate_id, {"name": f"Gate-{gate_id}"}), self.socketio
            )
        self.processors[gate_id].start(source)


# ─── Singleton Instance ───────────────────────────────────────────────────────
camera_manager = CameraManager()
