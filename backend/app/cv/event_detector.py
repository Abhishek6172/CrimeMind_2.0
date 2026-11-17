"""CCTV Event Detection Engine.
Extracts objective investigative events from object trajectories using neutral, verifiable descriptions.
"""

import math
from typing import Any, Dict, List


class CCTVEventDetector:
    """Detects spatial-temporal events from video detections and tracks."""

    def __init__(
        self,
        dwell_threshold_sec: float = 12.0,
        gathering_distance_px: float = 180.0,
        rapid_speed_px_sec: float = 240.0,
    ):
        self.dwell_threshold_sec = dwell_threshold_sec
        self.gathering_distance_px = gathering_distance_px
        self.rapid_speed_px_sec = rapid_speed_px_sec

    def extract_events(
        self,
        tracks: List[Dict[str, Any]],
        detections: List[Dict[str, Any]],
        video_id: int,
        camera_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Processes tracks and frames to extract verified investigative events."""
        events = []

        # 1. Prolonged Presence (Loitering) Event
        for t in tracks:
            dur = t.get("duration_sec", 0.0)
            if dur >= self.dwell_threshold_sec:
                cls_label = t.get("class_name", "object")
                events.append(
                    {
                        "event_type": "PROLONGED_PRESENCE",
                        "start_sec": t["first_seen_sec"],
                        "end_sec": t["last_seen_sec"],
                        "track_ids": [t["track_id"]],
                        "confidence": t["max_confidence"],
                        "description": (
                            f"Prolonged presence detected for {cls_label} (Track #{t['track_id']}) "
                            f"persisting {dur:.1f}s within surveillance perimeter."
                        ),
                        "frame_number": (
                            t["trajectory"][0]["frame"] if t.get("trajectory") else 0
                        ),
                    }
                )

        # 2. Rapid Acceleration / Movement
        for t in tracks:
            traj = t.get("trajectory", [])
            if len(traj) >= 3:
                # Check segment speeds
                for i in range(len(traj) - 1):
                    p1 = traj[i]
                    p2 = traj[i + 1]
                    dt = max(0.04, p2["sec"] - p1["sec"])
                    speed = math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"]) / dt
                    if speed > self.rapid_speed_px_sec:
                        events.append(
                            {
                                "event_type": "RAPID_MOVEMENT",
                                "start_sec": p1["sec"],
                                "end_sec": p2["sec"],
                                "track_ids": [t["track_id"]],
                                "confidence": round(t["max_confidence"] * 0.9, 2),
                                "description": (
                                    f"Rapid velocity transition observed for {t['class_name']} "
                                    f"(Track #{t['track_id']}, velocity {speed:.0f} px/s)."
                                ),
                                "frame_number": p1["frame"],
                            }
                        )
                        break

        # 3. Gathering Detection (Multiple persons co-present in spatial proximity)
        # Group person detections by frame
        person_frames: Dict[int, List[Dict[str, Any]]] = {}
        for d in detections:
            if d.get("class_name") == "person" and d.get("track_id") is not None:
                f_num = d["frame_number"]
                person_frames.setdefault(f_num, []).append(d)

        gathering_logged_times = set()
        for f_num, p_list in person_frames.items():
            if len(p_list) >= 3:
                # Check pairwise distances between centers
                t_sec = round(p_list[0]["timestamp_sec"], 0)
                if t_sec in gathering_logged_times:
                    continue

                close_group = []
                for i in range(len(p_list)):
                    for j in range(i + 1, len(p_list)):
                        b1 = p_list[i]["bbox"]
                        b2 = p_list[j]["bbox"]
                        c1 = ((b1[0] + b1[2]) / 2, (b1[1] + b1[3]) / 2)
                        c2 = ((b2[0] + b2[2]) / 2, (b2[1] + b2[3]) / 2)
                        if math.hypot(c1[0] - c2[0], c1[1] - c2[1]) < self.gathering_distance_px:
                            close_group.extend([p_list[i]["track_id"], p_list[j]["track_id"]])

                if len(set(close_group)) >= 3:
                    gathering_logged_times.add(t_sec)
                    t_ids = sorted(list(set(close_group)))
                    events.append(
                        {
                            "event_type": "GATHERING_DETECTED",
                            "start_sec": p_list[0]["timestamp_sec"],
                            "end_sec": round(p_list[0]["timestamp_sec"] + 3.0, 3),
                            "track_ids": t_ids,
                            "confidence": 0.88,
                            "description": (
                                f"Group gathering of {len(t_ids)} subjects detected in spatial cluster "
                                f"(Tracks: {', '.join(str(x) for x in t_ids)})."
                            ),
                            "frame_number": f_num,
                        }
                    )

        return sorted(events, key=lambda x: x["start_sec"])
