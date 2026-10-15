"""Alert Manager — triggers audio and dashboard alerts on PPE violations."""

import logging
import time
from datetime import datetime
from backend.config import ALERT_COOLDOWN_SEC, ALERT_AUDIO_ENABLED, ALERT_AUDIO_FILE

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alert throttling so the same gate doesn't spam alerts.
    {(gate_id, violation_type): last_alert_timestamp}
    """

    def __init__(self):
        self._last_alert: dict = {}

    def trigger(self, gate_id: int, gate_name: str, violation_type: str, violation_id: int):
        """Send alert for a violation — respects cooldown to avoid spam."""
        key = (gate_id, violation_type)
        now = time.time()
        last = self._last_alert.get(key, 0)

        if (now - last) < ALERT_COOLDOWN_SEC:
            return  # Suppress — within cooldown

        self._last_alert[key] = now

        logger.warning(f"🚨 ALERT: {violation_type} at {gate_name} (Violation #{violation_id})")

        if ALERT_AUDIO_ENABLED:
            self._play_audio()

    def _play_audio(self):
        """Play alert sound (non-blocking). Uses winsound on Windows."""
        try:
            import threading
            def _play():
                try:
                    import winsound
                    winsound.Beep(1000, 800)   # 1000 Hz for 800ms
                except Exception:
                    pass  # Audio optional
            threading.Thread(target=_play, daemon=True).start()
        except Exception as e:
            logger.debug(f"Audio alert skipped: {e}")


# ─── Singleton ────────────────────────────────────────────────────────────────
alert_manager = AlertManager()
