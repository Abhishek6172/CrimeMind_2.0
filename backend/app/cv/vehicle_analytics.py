"""Vehicle Analytics Engine.
Tracks motorized vehicles (cars, motorcycles, trucks, buses),
computes movement vectors, travel directions, and entry/exit patterns.
"""

import math
from typing import Any, Dict, List

VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}


class VehicleAnalyticsEngine:
    """Analyzes vehicle trajectory physics and flow patterns."""

    def analyze_tracks(
        self, tracks: List[Dict[str, Any]], video_width: int = 1920, video_height: int = 1080
    ) -> Dict[str, Any]:
        """Calculates direction vectors, speed estimates, and vehicle classification breakdown."""
        vehicle_tracks = [t for t in tracks if t.get("class_name") in VEHICLE_CLASSES]

        class_counts: Dict[str, int] = {}
        analyzed_vehicles = []

        for vt in vehicle_tracks:
            cls = vt["class_name"]
            class_counts[cls] = class_counts.get(cls, 0) + 1

            traj = vt.get("trajectory", [])
            direction = "STATIONARY"
            speed_px_sec = 0.0

            if len(traj) >= 2:
                p_start = traj[0]
                p_end = traj[-1]
                dx = p_end["x"] - p_start["x"]
                dy = p_end["y"] - p_start["y"]
                dt = max(0.1, p_end["sec"] - p_start["sec"])

                dist_px = math.hypot(dx, dy)
                speed_px_sec = round(dist_px / dt, 2)

                if dist_px > 30:
                    angle_deg = math.degrees(math.atan2(-dy, dx)) % 360  # image Y is downwards
                    if 45 <= angle_deg < 135:
                        direction = "NORTHBOUND"
                    elif 135 <= angle_deg < 225:
                        direction = "WESTBOUND"
                    elif 225 <= angle_deg < 315:
                        direction = "SOUTHBOUND"
                    else:
                        direction = "EASTBOUND"

            analyzed_vehicles.append(
                {
                    "track_id": vt["track_id"],
                    "class_name": cls,
                    "direction": direction,
                    "speed_px_sec": speed_px_sec,
                    "first_seen_sec": vt["first_seen_sec"],
                    "last_seen_sec": vt["last_seen_sec"],
                    "duration_sec": vt.get("duration_sec", 0.0),
                }
            )

        return {
            "total_vehicles_observed": len(vehicle_tracks),
            "class_distribution": class_counts,
            "vehicles": analyzed_vehicles,
        }
