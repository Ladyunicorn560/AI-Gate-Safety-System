"""
PPE Detection Module — Enhanced YOLOv8 Wrapper
Detects: Helmet, No-Helmet, Safety-Vest, No-Vest, Safety-Shoes, No-Shoes, Mask, No-Mask, Gloves, Person
Features: 2-Stage Person-Cropped Inference, Class-Adaptive Confidence, Anatomical Zone Verification.
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from backend.config import (
    PPE_MODEL_PATH, PPE_CONFIDENCE, PPE_IOU_THRESHOLD,
    PPE_IMAGE_SIZE, PPE_CLASSES, PPE_VIOLATION_CLASSES, PPE_CLASS_COLORS,
    PPE_CLASS_CONFIDENCE, PPE_IMAGE_SIZE_UPLOAD
)

logger = logging.getLogger(__name__)


class PPEDetector:
    """
    Wraps Ultralytics YOLOv8 with a 2-Stage Person-Cropped Inference Pipeline
    and Anatomical Zone Compliance verification for high-precision PPE auditing.
    """

    def __init__(self):
        self.model = None
        self.base_model = None
        self._initialized = False

    def initialize(self):
        """Load YOLOv8 PPE model and YOLOv8m base detector."""
        if self._initialized:
            return
        try:
            from ultralytics import YOLO

            # Load YOLOv8m (Medium) model for higher-precision person detection
            base_model_path = Path("yolov8m.pt")
            if base_model_path.exists():
                logger.info("Loading high-precision base model (yolov8m.pt)...")
                self.base_model = YOLO("yolov8m.pt")
            else:
                logger.info("Loading base YOLOv8 model (yolov8n.pt)...")
                self.base_model = YOLO("yolov8n.pt")

            model_path = Path(PPE_MODEL_PATH)
            if model_path.exists() and model_path.stat().st_size > 1000000:
                try:
                    logger.info(f"Loading custom PPE model from: {model_path}")
                    self.model = YOLO(str(model_path))
                except Exception as e:
                    logger.warning(f"Failed to load {model_path}: {e}. Falling back to base model.")
                    self.model = self.base_model
            else:
                self.model = self.base_model

            # Warm up models
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self.base_model.predict(dummy, verbose=False, device="cpu")
            self.model.predict(dummy, verbose=False, device="cpu")
            self._initialized = True
            logger.info("✅ Enhanced 2-Stage PPE & Base detection models loaded and ready.")
        except Exception as e:
            logger.error(f"❌ Failed to load PPE model: {e}")
            raise

    def _iou(self, boxA: list[int], boxB: list[int]) -> float:
        """Compute Intersection over Union (IoU) between two bounding boxes."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        if interArea <= 0:
            return 0.0
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        return interArea / float(boxAArea + boxBArea - interArea + 1e-6)

    def _normalize_class_name(self, raw_name: str) -> str:
        """Normalize PPE model label names to standard system classes."""
        lname = raw_name.lower().strip()
        if lname in ("hardhat", "helmet"):
            return "Helmet"
        elif lname in ("vest", "safety_vest", "safety-vest"):
            return "Safety-Vest"
        elif lname in ("goggles", "glasses"):
            return "Glasses"
        elif lname in ("safety_shoe", "safety-shoe", "shoes", "boots", "safety-shoes"):
            return "Safety-Shoes"
        elif lname in ("glove", "gloves"):
            return "Gloves"
        elif lname == "mask":
            return "Mask"
        elif lname == "person":
            return "Person"
        return raw_name.title()

    def _get_class_threshold(self, norm_name: str) -> float:
        """Get class-specific confidence threshold."""
        key = norm_name.lower()
        return PPE_CLASS_CONFIDENCE.get(key, PPE_CONFIDENCE)

    def detect(self, frame: np.ndarray, imgsz: int = None, use_crops: bool = True) -> list[dict]:
        """
        Run 2-Stage PPE detection on a single frame.
        1. Full-frame pass for Persons and general objects.
        2. Cropped Person pass for small equipment (Helmets, Vests, Shoes, Gloves, Masks).
        3. Anatomical Zone verification for missing PPE.
        """
        if not self._initialized:
            raise RuntimeError("PPEDetector not initialized. Call initialize() first.")

        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
        img_size = imgsz if imgsz else PPE_IMAGE_SIZE
        raw_detections = []

        # ── 1. Base Model Pass (Full Frame) ──────────────────────────────────
        if self.base_model:
            base_results = self.base_model.predict(
                frame,
                conf=0.20,
                iou=PPE_IOU_THRESHOLD,
                imgsz=img_size,
                device="cpu",
                verbose=False,
            )[0]

            for box in base_results.boxes:
                cls_id = int(box.cls[0])
                class_name = base_results.names.get(cls_id, f"class_{cls_id}")
                if class_name.lower() == "person":
                    conf = float(box.conf[0])
                    bbox = [int(v) for v in box.xyxy[0].tolist()]
                    raw_detections.append({
                        "class_id": cls_id,
                        "class_name": "Person",
                        "confidence": round(conf, 4),
                        "bbox": bbox,
                        "is_violation": False,
                        "source": "base_full",
                    })

        # ── 2. PPE Model Pass (Full Frame) ───────────────────────────────────
        ppe_results = self.model.predict(
            frame,
            conf=0.12,  # Low initial cutoff, filtered by class-adaptive thresholds below
            iou=PPE_IOU_THRESHOLD,
            imgsz=img_size,
            device="cpu",
            verbose=False,
        )[0]

        for box in ppe_results.boxes:
            cls_id = int(box.cls[0])
            conf   = float(box.conf[0])
            bbox   = [int(v) for v in box.xyxy[0].tolist()]
            raw_name = ppe_results.names.get(cls_id, PPE_CLASSES.get(cls_id, f"class_{cls_id}"))
            norm_name = self._normalize_class_name(raw_name)

            if conf < self._get_class_threshold(norm_name):
                continue

            raw_detections.append({
                "class_id":    cls_id,
                "class_name":  norm_name,
                "confidence":  round(conf, 4),
                "bbox":        bbox,
                "is_violation": self._is_violation(raw_name),
                "source":      "ppe_full",
            })

        # ── 3. Stage-2 Person Crops Pass ─────────────────────────────────────
        if use_crops:
            persons = [d for d in raw_detections if d["class_name"].lower() == "person"]
            for person in persons:
                px1, py1, px2, py2 = person["bbox"]
                pw, ph = px2 - px1, py2 - py1

                if pw < 30 or ph < 40:
                    continue  # Skip tiny distant figures

                # Crop person region with 10% padding
                cx1 = max(0, int(px1 - 0.10 * pw))
                cy1 = max(0, int(py1 - 0.10 * ph))
                cx2 = min(w, int(px2 + 0.10 * pw))
                cy2 = min(h, int(py2 + 0.10 * ph))

                person_crop = frame[cy1:cy2, cx1:cx2]
                if person_crop.size == 0:
                    continue

                crop_results = self.model.predict(
                    person_crop,
                    conf=0.12,
                    iou=0.35,
                    imgsz=640,
                    device="cpu",
                    verbose=False,
                )[0]

                for box in crop_results.boxes:
                    cls_id = int(box.cls[0])
                    conf   = float(box.conf[0])
                    c_name = crop_results.names.get(cls_id, f"class_{cls_id}")
                    norm_name = self._normalize_class_name(c_name)

                    if norm_name.lower() == "person":
                        continue  # Skip duplicate person boxes in crops

                    if conf < self._get_class_threshold(norm_name):
                        continue

                    # Map crop bounding box coordinates back to full image
                    bx1, by1, bx2, by2 = [int(v) for v in box.xyxy[0].tolist()]
                    gx1, gy1 = bx1 + cx1, by1 + cy1
                    gx2, gy2 = bx2 + cx1, by2 + cy1

                    raw_detections.append({
                        "class_id":    cls_id,
                        "class_name":  norm_name,
                        "confidence":  round(conf, 4),
                        "bbox":        [gx1, gy1, gx2, gy2],
                        "is_violation": self._is_violation(c_name),
                        "source":      "ppe_crop",
                    })

        # ── 4. Visual Feature PPE Enrichment (Color & High-Vis Heuristics) ────
        enriched_detections = self._apply_visual_ppe_enrichment(frame, raw_detections)

        # ── 5. Non-Maximum Suppression / Deduplication ───────────────────────
        final_detections = self._suppress_duplicates(enriched_detections)

        return final_detections

    def _suppress_duplicates(self, detections: list[dict]) -> list[dict]:
        """Merge duplicate detections for the same class with strict IoU deduplication."""
        sorted_dets = sorted(detections, key=lambda x: x["confidence"], reverse=True)
        kept = []

        for det in sorted_dets:
            duplicate = False
            d_cls = det["class_name"].lower()
            d_box = det["bbox"]

            for k in kept:
                k_cls = k["class_name"].lower()
                if d_cls == k_cls:
                    # Strict IoU cutoff (0.15) for gear labels to eliminate duplicate boxes on same person
                    iou_val = self._iou(d_box, k["bbox"])
                    if iou_val > 0.15:
                        duplicate = True
                        break
                    # Also check if centers of bounding boxes are close to each other
                    dc_x, dc_y = (d_box[0] + d_box[2]) / 2.0, (d_box[1] + d_box[3]) / 2.0
                    kc_x, kc_y = (k["bbox"][0] + k["bbox"][2]) / 2.0, (k["bbox"][1] + k["bbox"][3]) / 2.0
                    if abs(dc_x - kc_x) < 0.25 * (d_box[2] - d_box[0]) and abs(dc_y - kc_y) < 0.25 * (d_box[3] - d_box[1]):
                        duplicate = True
                        break
            if not duplicate:
                kept.append(det)

        return kept

    def _apply_visual_ppe_enrichment(self, frame: np.ndarray, detections: list[dict]) -> list[dict]:
        """
        Enriches detections by analyzing high-visibility HSV colors and hardhat/footwear
        visual features on cropped person regions.
        """
        if frame is None or frame.size == 0:
            return detections

        h, w = frame.shape[:2]
        persons = [d for d in detections if d["class_name"].lower() == "person"]
        additional_gear = []

        for p in persons:
            px1, py1, px2, py2 = p["bbox"]
            pw, ph = px2 - px1, py2 - py1

            if pw < 30 or ph < 50:
                continue

            person_crop = frame[max(0, py1):min(h, py2), max(0, px1):min(w, px2)]
            if person_crop.size == 0:
                continue

            ch, cw = person_crop.shape[:2]
            hsv = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)

            # Define Anatomical Regions in Person Crop
            head_box  = [px1, py1, px2, py1 + int(0.30 * ph)]
            torso_box = [px1, py1 + int(0.20 * ph), px2, py1 + int(0.75 * ph)]
            feet_box  = [px1, py2 - int(0.25 * ph), px2, py2]

            has_helmet = any(("helmet" in d["class_name"].lower() or "hardhat" in d["class_name"].lower()) and self._iou(d["bbox"], head_box) > 0.05 for d in detections)
            has_vest   = any(("vest" in d["class_name"].lower()) and self._iou(d["bbox"], torso_box) > 0.05 for d in detections)
            has_shoes  = any(("shoe" in d["class_name"].lower() or "boot" in d["class_name"].lower()) and self._iou(d["bbox"], feet_box) > 0.05 for d in detections)

            # 1. Head Zone Hardhat Color Check (Yellow, Orange, Red, White, Blue)
            if not has_helmet:
                head_hsv = hsv[0:int(0.28 * ch), :]
                if head_hsv.size > 0:
                    yellow_m = cv2.inRange(head_hsv, (15, 60, 90), (35, 255, 255))
                    orange_m = cv2.inRange(head_hsv, (0, 60, 90), (15, 255, 255))
                    white_m  = cv2.inRange(head_hsv, (0, 0, 170), (180, 45, 255))
                    blue_m   = cv2.inRange(head_hsv, (90, 60, 90), (130, 255, 255))
                    
                    tot_head_px = head_hsv.shape[0] * head_hsv.shape[1]
                    hardhat_px = np.count_nonzero(yellow_m | orange_m | white_m | blue_m)
                    if (hardhat_px / float(tot_head_px)) >= 0.10:
                        additional_gear.append({
                            "class_id": 0,
                            "class_name": "Helmet",
                            "confidence": 0.88,
                            "bbox": [px1 + int(0.15 * pw), py1, px2 - int(0.15 * pw), py1 + int(0.25 * ph)],
                            "is_violation": False,
                            "source": "color_heuristic",
                        })

            # 2. Torso Zone High-Vis Vest Check (Neon Yellow/Green, Hi-Vis Orange, Reflective Pink/Red)
            if not has_vest:
                torso_hsv = hsv[int(0.20 * ch):int(0.75 * ch), :]
                if torso_hsv.size > 0:
                    neon_yellow  = cv2.inRange(torso_hsv, (18, 60, 80), (45, 255, 255))
                    hivis_orange = cv2.inRange(torso_hsv, (0, 60, 80), (18, 255, 255))
                    hivis_pink   = cv2.inRange(torso_hsv, (150, 45, 80), (180, 255, 255))
                    
                    tot_torso_px = torso_hsv.shape[0] * torso_hsv.shape[1]
                    vest_px = np.count_nonzero(neon_yellow | hivis_orange | hivis_pink)
                    if (vest_px / float(tot_torso_px)) >= 0.12:
                        additional_gear.append({
                            "class_id": 2,
                            "class_name": "Safety-Vest",
                            "confidence": 0.85,
                            "bbox": [px1 + int(0.05 * pw), py1 + int(0.20 * ph), px2 - int(0.05 * pw), py1 + int(0.70 * ph)],
                            "is_violation": False,
                            "source": "color_heuristic",
                        })

            # 3. Footwear Zone Check — Only run if person box aspect ratio confirms full-body head-to-toe pose
            is_full_body = (ph / float(pw) >= 2.2) and (py2 >= 0.85 * h) and (ph > 220)
            if not has_shoes and is_full_body:
                foot_hsv = hsv[int(0.75 * ch):, :]
                if foot_hsv.size > 0:
                    tot_foot_px = foot_hsv.shape[0] * foot_hsv.shape[1]
                    dark_boot  = cv2.inRange(foot_hsv, (0, 0, 0), (180, 255, 120))
                    brown_boot = cv2.inRange(foot_hsv, (0, 30, 30), (25, 255, 170))
                    boot_px = np.count_nonzero(dark_boot | brown_boot)
                    if (boot_px / float(tot_foot_px)) >= 0.18:
                        additional_gear.append({
                            "class_id": 4,
                            "class_name": "Safety-Shoes",
                            "confidence": 0.82,
                            "bbox": [px1 + int(0.10 * pw), py2 - int(0.20 * ph), px2 - int(0.10 * pw), py2],
                            "is_violation": False,
                            "source": "color_heuristic",
                        })

        return detections + additional_gear

    def _is_violation(self, class_name: str) -> bool:
        """Check if a detected class is a PPE violation."""
        violation_keywords = ["no_helmet", "no-helmet", "no_hardhat", "no_vest",
                               "no-vest", "no_shoes", "no-shoes", "no_mask", "no-mask",
                               "no_gloves", "no-gloves", "no_glasses", "no-glasses",
                               "no_ear", "no-ear", "without_helmet", "without_vest"]
        return any(kw in class_name.lower() for kw in violation_keywords)

    def get_violations(self, detections: list[dict]) -> list[dict]:
        """Filter only violation detections from a full detection list."""
        return [d for d in detections if d["is_violation"]]

    def draw_detections(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels on frame."""
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            class_name = det["class_name"]
            conf       = det["confidence"]
            is_violation = det["is_violation"]

            # Color: Red for violations, PPE_CLASS_COLORS lookup or default
            if is_violation:
                color = (0, 0, 220)
            elif class_name in PPE_CLASS_COLORS:
                color = PPE_CLASS_COLORS[class_name]
            elif class_name.lower() == "person":
                color = (255, 165, 0)
            else:
                color = (0, 210, 0)

            # Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Label background
            label = f"{class_name} {conf:.0%}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - lh - 8), (x1 + lw + 4, y1), color, -1)
            cv2.putText(frame, label, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            # Violation badge
            if is_violation:
                cv2.putText(frame, "⚠ VIOLATION", (x1, y2 + 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        return frame

    def overlay_stats(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Add a stats overlay showing counts of PPE items on frame."""
        violations = self.get_violations(detections)
        persons    = [d for d in detections if d["class_name"].lower() == "person"]

        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (280, 80), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        cv2.putText(frame, f"Persons: {len(persons)}", (15, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        violation_color = (0, 0, 255) if violations else (0, 255, 0)
        cv2.putText(frame, f"Violations: {len(violations)}", (15, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, violation_color, 2)
        return frame


# ─── Singleton Instance ───────────────────────────────────────────────────────
ppe_detector = PPEDetector()

