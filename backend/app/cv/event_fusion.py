"""Multimodal Event Fusion Engine.
Correlates visual detections, movement trajectories, audio anomalies,
and multi-camera observations into a unified investigative timeline.
"""

from typing import Any, Dict, List


class MultimodalFusionEngine:
    """Fuses disparate sensory events across space and time."""

    def __init__(self, temporal_window_sec: float = 30.0):
        self.temporal_window_sec = temporal_window_sec

    def fuse_events(
        self,
        visual_events: List[Dict[str, Any]],
        audio_events: List[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        """Identifies temporal coincidences between visual and audio occurrences."""
        correlations = []
        audio_events = audio_events or []

        # Correlate sequential visual events
        for i in range(len(visual_events)):
            for j in range(i + 1, len(visual_events)):
                ev1 = visual_events[i]
                ev2 = visual_events[j]
                time_diff = abs(ev2["start_sec"] - ev1["start_sec"])

                if time_diff <= self.temporal_window_sec:
                    correlations.append(
                        {
                            "primary_event_id": ev1.get("event_id"),
                            "correlated_event_id": ev2.get("event_id"),
                            "correlation_type": "SEQUENTIAL_MOVEMENT",
                            "time_diff_sec": round(time_diff, 2),
                            "confidence": 0.82,
                            "description": (
                                f"Observed {ev1['event_type']} followed by {ev2['event_type']} "
                                f"within {time_diff:.1f}s window."
                            ),
                        }
                    )

        # Correlate visual events with audio events
        for vev in visual_events:
            for aev in audio_events:
                t_diff = abs(aev["start_sec"] - vev["start_sec"])
                if t_diff <= 10.0:
                    correlations.append(
                        {
                            "primary_event_id": vev.get("event_id"),
                            "audio_event_id": aev.get("audio_event_id"),
                            "correlation_type": "AUDIO_VISUAL_SYNC",
                            "time_diff_sec": round(t_diff, 2),
                            "confidence": 0.88,
                            "description": (
                                f"Visual event {vev['event_type']} synchronized with acoustic anomaly "
                                f"'{aev['sound_category']}' (Δt={t_diff:.1f}s)."
                            ),
                        }
                    )

        return correlations
