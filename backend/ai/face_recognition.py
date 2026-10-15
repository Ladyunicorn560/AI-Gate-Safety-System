"""
Face Recognition Module — InsightFace Wrapper
Handles: enrollment, real-time identification, similarity scoring.
"""

import logging
import numpy as np
import cv2
import os
import pickle
from pathlib import Path
from datetime import datetime
from backend.config import (
    FACE_MODEL_NAME, FACE_RECOGNITION_THRESHOLD,
    FACE_PROVIDERS, FACE_CTX_ID, EMPLOYEE_FACES_DIR
)

logger = logging.getLogger(__name__)


class FaceRecognizer:
    """
    Wraps InsightFace FaceAnalysis for enrollment and real-time recognition.
    Uses buffalo_l model (SCRFD detector + ResNet50 recognizer).
    """

    def __init__(self):
        self.app = None
        self.known_embeddings: list[dict] = []   # [{employee_id, full_name, emp_code, embedding}]
        self._initialized = False

    def initialize(self):
        """Load InsightFace model. Call once at startup."""
        if self._initialized:
            return
        try:
            import insightface
            from insightface.app import FaceAnalysis

            logger.info(f"Loading InsightFace model '{FACE_MODEL_NAME}' (CPU)...")
            self.app = FaceAnalysis(
                name=FACE_MODEL_NAME,
                providers=FACE_PROVIDERS
            )
            self.app.prepare(ctx_id=FACE_CTX_ID, det_size=(640, 640))
            self._initialized = True
            logger.info("[OK] InsightFace face recognition model loaded.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load InsightFace: {e}")
            raise

    def load_known_faces(self, employee_list: list):
        """
        Load all enrolled employee embeddings into memory for fast matching.
        employee_list: output of EmployeeModel.get_all_enrolled_faces()
        """
        self.known_embeddings = [
            {
                "employee_id": emp["employee_id"],
                "emp_code":    emp["emp_code"],
                "full_name":   emp["full_name"],
                "department":  emp["department"],
                "emp_type":    emp["emp_type"],
                "embedding":   np.array(emp["embedding"], dtype=np.float32),
            }
            for emp in employee_list
        ]
        logger.info(f"[OK] Loaded {len(self.known_embeddings)} enrolled face embeddings.")

    def detect_faces(self, frame: np.ndarray) -> list:
        """
        Detect all faces in a frame.
        Returns list of InsightFace Face objects with .embedding, .bbox, .det_score
        """
        if not self._initialized:
            raise RuntimeError("FaceRecognizer not initialized. Call initialize() first.")
        faces = self.app.get(frame)
        return faces

    def identify(self, face_embedding: np.ndarray) -> dict | None:
        """
        Match a detected face embedding against all enrolled faces.
        Returns the best match dict or None if no match above threshold.
        """
        if not self.known_embeddings:
            return None

        best_match = None
        best_score = -1.0

        # Normalize query embedding
        query = face_embedding / (np.linalg.norm(face_embedding) + 1e-6)

        for emp in self.known_embeddings:
            known = emp["embedding"] / (np.linalg.norm(emp["embedding"]) + 1e-6)
            score = float(np.dot(query, known))  # Cosine similarity
            if score > best_score:
                best_score = score
                best_match = emp

        if best_score >= FACE_RECOGNITION_THRESHOLD and best_match:
            return {**best_match, "confidence": round(best_score, 4)}
        return None

    def process_frame(self, frame: np.ndarray) -> list[dict]:
        """
        Full pipeline: detect all faces in frame + identify each.
        Returns list of recognition results per detected face.
        """
        results = []
        try:
            faces = self.detect_faces(frame)
            for face in faces:
                match = self.identify(face.embedding)
                bbox = face.bbox.astype(int).tolist()
                results.append({
                    "bbox":       bbox,           # [x1, y1, x2, y2]
                    "det_score":  float(face.det_score),
                    "matched":    match is not None,
                    "employee":   match,
                })
        except Exception as e:
            logger.error(f"Face processing error: {e}")
        return results

    def enroll_from_image(self, image_path: str) -> np.ndarray | None:
        """
        Extract face embedding from an enrollment image.
        Returns 512-d embedding array or None if no clear face found.
        """
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Cannot read image: {image_path}")
            return None
        faces = self.detect_faces(img)
        if not faces:
            logger.warning(f"No face detected in: {image_path}")
            return None
        if len(faces) > 1:
            logger.warning(f"Multiple faces in enrollment image — using largest.")
            # Pick face with largest bounding box area
            faces = sorted(faces, key=lambda f: (f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1]), reverse=True)
        return faces[0].embedding

    def enroll_from_frame(self, frame: np.ndarray, employee_id: int) -> tuple[np.ndarray | None, str | None]:
        """
        Enroll a face from a camera frame.
        Saves cropped face image to EMPLOYEE_FACES_DIR.
        Returns (embedding, saved_photo_path) or (None, None)
        """
        faces = self.detect_faces(frame)
        if not faces:
            return None, None

        # Pick the most prominent (highest detection score) face
        face = max(faces, key=lambda f: f.det_score)

        # Crop and save face photo
        x1, y1, x2, y2 = face.bbox.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        face_crop = frame[y1:y2, x1:x2]

        photo_filename = f"emp_{employee_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        photo_path = str(Path(EMPLOYEE_FACES_DIR) / photo_filename)
        cv2.imwrite(photo_path, face_crop)

        return face.embedding, photo_path

    def draw_results(self, frame: np.ndarray, results: list[dict]) -> np.ndarray:
        """Draw recognition results (bounding boxes + names) on frame."""
        for res in results:
            x1, y1, x2, y2 = res["bbox"]
            if res["matched"]:
                emp = res["employee"]
                color = (0, 255, 0)  # Green for recognized
                label = f"{emp['full_name']} ({emp['confidence']:.0%})"
            else:
                color = (0, 165, 255)  # Orange for unknown
                label = f"Unknown ({res['det_score']:.0%})"

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.rectangle(frame, (x1, y1 - 25), (x2, y1), color, -1)
            cv2.putText(frame, label, (x1 + 4, y1 - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
        return frame


# ─── Singleton Instance ───────────────────────────────────────────────────────
face_recognizer = FaceRecognizer()
