"""Person Analytics Engine.
Derives high-level investigative signals from person detections and tracks:
appearance timelines, dwell times, entry/exit trajectories, and multi-appearance frequency.
"""

from typing import Any, Dict, List


class PersonAnalyticsEngine:
    """Analyzes person trajectories and presence cadences."""

    def __init__(self, loiter_threshold_sec: float = 15.0):
        self.loiter_threshold_sec = loiter_threshold_sec

    def analyze_tracks(
        self, tracks: List[Dict[str, Any]], video_width: int = 1920, video_height: int = 1080
    ) -> Dict[str, Any]:
        """Processes person tracks and extracts behavioural metrics."""
        person_tracks = [t for t in tracks if t.get("class_name") == "person"]

        total_persons_observed = len(person_tracks)
        loitering_subjects = []
        entry_exit_events = []

        # Border zones for entry/exit (e.g. 5% from edges)
        border_x = video_width * 0.08
        border_y = video_height * 0.08

        for pt in person_tracks:
            tid = pt["track_id"]
            dur = pt.get("duration_sec", 0.0)
            traj = pt.get("trajectory", [])

            # Check for prolonged dwell time (loitering)
            if dur >= self.loiter_threshold_sec:
                loitering_subjects.append(
                    {
                        "track_id": tid,
                        "duration_sec": dur,
                        "first_seen": pt["first_seen_sec"],
                        "last_seen": pt["last_seen_sec"],
                        "confidence": pt["max_confidence"],
                    }
                )

            # Analyze trajectory direction and entry/exit
            if len(traj) >= 2:
                start_pt = traj[0]
                end_pt = traj[-1]

                is_entry = (
                    start_pt["x"] < border_x
                    or start_pt["x"] > (video_width - border_x)
                    or start_pt["y"] < border_y
                    or start_pt["y"] > (video_height - border_y)
                )
                is_exit = (
                    end_pt["x"] < border_x
                    or end_pt["x"] > (video_width - border_x)
                    or end_pt["y"] < border_y
                    or end_pt["y"] > (video_height - border_y)
                )

                if is_entry:
                    entry_exit_events.append(
                        {
                            "type": "PERSON_ENTRY",
                            "track_id": tid,
                            "timestamp_sec": start_pt["sec"],
                            "position": [start_pt["x"], start_pt["y"]],
                        }
                    )
                if is_exit:
                    entry_exit_events.append(
                        {
                            "type": "PERSON_EXIT",
                            "track_id": tid,
                            "timestamp_sec": end_pt["sec"],
                            "position": [end_pt["x"], end_pt["y"]],
                        }
                    )

        return {
            "total_persons_observed": total_persons_observed,
            "loitering_subjects": loitering_subjects,
            "entry_exit_events": sorted(entry_exit_events, key=lambda x: x["timestamp_sec"]),
            "average_dwell_sec": (
                round(sum(t.get("duration_sec", 0) for t in person_tracks) / total_persons_observed, 2)
                if total_persons_observed > 0
                else 0.0
            ),
        }
