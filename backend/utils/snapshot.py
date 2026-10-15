"""Snapshot utility — saves violation images with metadata."""

import cv2
import logging
import os
from datetime import datetime
from pathlib import Path
from backend.config import VIOLATIONS_DIR, SNAPSHOT_QUALITY, SNAPSHOT_RETENTION_DAYS

logger = logging.getLogger(__name__)


def save_violation_snapshot(frame, gate_id: int, violation_type: str) -> str:
    """
    Save a violation frame as JPEG.
    Returns the relative path stored in DB.
    """
    try:
        # Folder: violations/gate_{id}/2026-09-06/
        date_str = datetime.now().strftime("%Y-%m-%d")
        folder = Path(VIOLATIONS_DIR) / f"gate_{gate_id}" / date_str
        folder.mkdir(parents=True, exist_ok=True)

        # Filename: violation_NoHelmet_143022.jpg
        safe_type = violation_type.replace(" ", "_").replace("/", "_")
        time_str  = datetime.now().strftime("%H%M%S_%f")[:11]
        filename  = f"violation_{safe_type}_{time_str}.jpg"
        filepath  = folder / filename

        cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_QUALITY])
        logger.debug(f"Snapshot saved: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Snapshot save failed: {e}")
        return ""


def cleanup_old_snapshots():
    """
    Delete snapshots older than SNAPSHOT_RETENTION_DAYS (90 days).
    Call this on a daily schedule.
    """
    import shutil
    cutoff = datetime.now().timestamp() - (SNAPSHOT_RETENTION_DAYS * 86400)
    deleted = 0
    for root, dirs, files in os.walk(VIOLATIONS_DIR):
        for file in files:
            fp = Path(root) / file
            if fp.stat().st_mtime < cutoff:
                fp.unlink()
                deleted += 1
    logger.info(f"Cleanup: Deleted {deleted} old snapshots (>{SNAPSHOT_RETENTION_DAYS} days).")
    return deleted
