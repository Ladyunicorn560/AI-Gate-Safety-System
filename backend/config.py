"""
AI Gate Safety System — Central Configuration
All settings, paths, and constants in one place.
"""

import os
from pathlib import Path

# ─── Base Paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
VIOLATIONS_DIR = DATA_DIR / "violations"
EMPLOYEE_FACES_DIR = DATA_DIR / "employee_faces"
REPORTS_DIR = DATA_DIR / "reports"
UPLOADS_DIR = DATA_DIR / "uploads"

# Create directories if they don't exist
for d in [DATA_DIR, MODELS_DIR, VIOLATIONS_DIR, EMPLOYEE_FACES_DIR, REPORTS_DIR, UPLOADS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Database (Microsoft SQL Server — Windows Authentication) ─────────────────
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_NAME   = os.getenv("DB_NAME",   "AI_Gate_Safety_DB")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")

# pyodbc connection string — Windows Auth (no username/password)
DB_CONNECTION_STRING = (
    f"DRIVER={{{DB_DRIVER}}};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"Trusted_Connection=yes;"
    f"TrustServerCertificate=yes;"
)

DB_POOL_SIZE = 10
DB_TIMEOUT   = 30  # seconds

# ─── Flask / API ──────────────────────────────────────────────────────────────
FLASK_HOST       = "0.0.0.0"
FLASK_PORT       = int(os.getenv("PORT", 5000))
FLASK_DEBUG      = os.getenv("FLASK_DEBUG", "false").lower() == "true"
SECRET_KEY       = os.getenv("SECRET_KEY", "change-this-secret-key-before-running")
JWT_EXPIRES_HOURS = 8

# ─── InsightFace (Face Recognition) ──────────────────────────────────────────
FACE_MODEL_NAME       = "buffalo_l"        # Auto-downloads ~326MB on first run
FACE_RECOGNITION_THRESHOLD = 0.4          # Cosine similarity threshold (lower = stricter)
FACE_DETECTION_SIZE   = (640, 640)
FACE_CTX_ID           = 0                 # CPU = 0
FACE_PROVIDERS        = ["CPUExecutionProvider"]

# ─── YOLOv8 PPE Detection ─────────────────────────────────────────────────────
PPE_MODEL_PATH        = str(MODELS_DIR / "ppe_model.pt")
PPE_CONFIDENCE        = 0.25              # Base confidence threshold for persons/general objects
PPE_IOU_THRESHOLD     = 0.45
PPE_IMAGE_SIZE        = 640
PPE_IMAGE_SIZE_UPLOAD = 1024            # Higher resolution for uploads / test playground

# Class-specific confidence cutoffs (tailored for small/low-contrast objects)
PPE_CLASS_CONFIDENCE = {
    "person":       0.25,
    "helmet":       0.18,
    "hardhat":      0.18,
    "vest":         0.18,
    "safety-vest":  0.18,
    "mask":         0.15,
    "gloves":       0.15,
    "goggles":      0.15,
    "glasses":      0.15,
    "safety-shoes": 0.15,
    "shoes":        0.15,
    "safety_shoe":  0.15,
}

# PPE Classes — what the model detects
PPE_CLASSES = {
    0:  "Helmet",
    1:  "No-Helmet",
    2:  "Safety-Vest",
    3:  "No-Vest",
    4:  "Safety-Shoes",
    5:  "No-Shoes",
    6:  "Mask",
    7:  "No-Mask",
    8:  "Person",
    9:  "Gloves",
    10: "No-Gloves",
    11: "Glasses",
    12: "No-Glasses",
    13: "Ear",
    14: "Hands",
}

# Classes that are PPE VIOLATIONS (trigger alerts)
PPE_VIOLATION_CLASSES = {1, 3, 5, 7, 10, 12}  # No-Helmet, No-Vest, No-Shoes, No-Mask, No-Gloves, No-Glasses

# Color mapping for bounding boxes (BGR for OpenCV)
PPE_CLASS_COLORS = {
    "Helmet":      (0, 255, 0),    # Green
    "No-Helmet":   (0, 0, 255),    # Red
    "Safety-Vest": (0, 255, 128),  # Light Green
    "No-Vest":     (0, 0, 200),    # Dark Red
    "Safety-Shoes":(0, 200, 0),    # Green
    "No-Shoes":    (0, 50, 255),   # Red-Orange
    "Mask":        (255, 200, 0),  # Cyan
    "No-Mask":     (0, 0, 255),    # Red
    "Person":      (255, 165, 0),  # Orange
    "Gloves":      (0, 255, 200),  # Teal
    "No-Gloves":   (0, 100, 255),  # Red
    "Glasses":     (255, 0, 255),  # Purple
    "No-Glasses":  (0, 0, 255),    # Red
    "Ear":         (255, 255, 0),  # Yellow
    "Hands":       (255, 128, 0),  # Light Blue
}

# ─── Camera / Gate Configuration ─────────────────────────────────────────────
# Format: { gate_id: { name, rtsp_url, location } }
GATES = {
    1: {"name": "Main Gate-1", "location": "North Entrance",  "rtsp_url": os.getenv("GATE1_RTSP", "")},
    2: {"name": "Main Gate-2", "location": "South Entrance",  "rtsp_url": os.getenv("GATE2_RTSP", "")},
    3: {"name": "Main Gate-3", "location": "East Entrance",   "rtsp_url": os.getenv("GATE3_RTSP", "")},
    4: {"name": "Main Gate-4", "location": "West Entrance",   "rtsp_url": os.getenv("GATE4_RTSP", "")},
}

CAMERA_FPS        = 10   # Process N frames per second (lower = less CPU load)
CAMERA_RECONNECT_DELAY = 5  # Seconds before retrying a failed camera connection

# ─── Attendance ───────────────────────────────────────────────────────────────
ATTENDANCE_COOLDOWN_MINUTES = 10  # Prevent duplicate attendance logs within N minutes
SHIFTS = {
    "A": {"name": "Morning Shift",   "start": "06:00", "end": "14:00"},
    "B": {"name": "Afternoon Shift", "start": "14:00", "end": "22:00"},
    "C": {"name": "Night Shift",     "start": "22:00", "end": "06:00"},
    "G": {"name": "General Shift",   "start": "08:00", "end": "17:00"},
}

# ─── Snapshot / Storage ───────────────────────────────────────────────────────
SNAPSHOT_QUALITY        = 95       # JPEG quality (1-100)
SNAPSHOT_RETENTION_DAYS = 90       # Auto-delete snapshots older than 90 days
SNAPSHOT_MAX_SIZE_MB    = 500      # Warn when violations folder exceeds this

# ─── Alerts ───────────────────────────────────────────────────────────────────
ALERT_AUDIO_ENABLED = True
ALERT_AUDIO_FILE    = str(BASE_DIR / "frontend" / "assets" / "alert.mp3")
ALERT_COOLDOWN_SEC  = 30    # Don't re-alert for same person/violation within N seconds

# ─── Reports ──────────────────────────────────────────────────────────────────
REPORT_COMPANY_NAME = "AI Gate Safety System"
REPORT_LOGO_PATH    = str(BASE_DIR / "frontend" / "assets" / "logo.png")
REPORT_FORMATS      = ["excel", "pdf"]

# ─── Roles & Permissions ─────────────────────────────────────────────────────
ROLES = {
    "admin":    {"label": "Administrator", "permissions": ["all"]},
    "security": {"label": "Security",      "permissions": ["view_live", "view_attendance", "view_violations"]},
    "hr":       {"label": "HR",            "permissions": ["view_attendance", "view_employees", "reports"]},
    "safety":   {"label": "Safety Officer","permissions": ["view_live", "view_violations", "reports"]},
}

# ─── Logging ─────────────────────────────────────────────────────────────────
LOG_DIR   = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_LEVEL = "INFO"
LOG_FILE  = str(LOG_DIR / "app.log")
