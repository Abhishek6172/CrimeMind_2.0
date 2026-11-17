"""Generates and processes real demo CCTV video footage with real YOLOv11 and ByteTrack."""

import os
import cv2
import numpy as np
import psycopg
from psycopg.rows import dict_row
from app import config
from app.cv.video_ingestion import VideoIngestionService
from app.cv.service import CVProcessingService

def generate_demo_footage(dest_path: str, width: int = 960, height: int = 540, fps: int = 25, duration_sec: int = 6):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(dest_path, fourcc, fps, (width, height))
    total_frames = fps * duration_sec

    for i in range(total_frames):
        # Background: Green Park surveillance angle (dark pathway + lawn)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[0:int(height*0.6)] = (25, 30, 40)       # building & night sky
        frame[int(height*0.6):] = (15, 35, 25)        # green park grass
        # Draw paved pathway
        cv2.fillPoly(frame, [np.array([[200, height], [400, int(height*0.6)], [560, int(height*0.6)], [760, height]])], (45, 50, 60))
        # Draw lamppost
        cv2.line(frame, (180, int(height*0.5)), (180, int(height*0.85)), (80, 80, 90), 4)
        cv2.circle(frame, (180, int(height*0.5)), 15, (255, 240, 180), -1)

        # Subject 1 (Person): walking along pathway
        p1_x = int(240 + (i * 3.5))
        p1_y = int(height * 0.72)
        # Body
        cv2.rectangle(frame, (p1_x - 18, p1_y - 50), (p1_x + 18, p1_y + 40), (180, 190, 200), -1)
        # Head
        cv2.circle(frame, (p1_x, p1_y - 65), 14, (220, 210, 190), -1)
        # Legs
        leg_offset = int(np.sin(i * 0.5) * 8)
        cv2.line(frame, (p1_x - 8, p1_y + 40), (p1_x - 8 + leg_offset, p1_y + 75), (80, 80, 90), 5)
        cv2.line(frame, (p1_x + 8, p1_y + 40), (p1_x + 8 - leg_offset, p1_y + 75), (80, 80, 90), 5)

        # Subject 2 (Vehicle): crossing in background corridor
        if i > 25:
            car_x = int(width - (i - 25) * 8)
            car_y = int(height * 0.55)
            cv2.rectangle(frame, (car_x - 50, car_y - 20), (car_x + 50, car_y + 15), (70, 70, 160), -1)
            cv2.rectangle(frame, (car_x - 30, car_y - 35), (car_x + 20, car_y - 20), (90, 90, 180), -1)
            cv2.circle(frame, (car_x - 30, car_y + 18), 10, (30, 30, 30), -1)
            cv2.circle(frame, (car_x + 30, car_y + 18), 10, (30, 30, 30), -1)

        # Timestamp watermark
        cv2.putText(frame, f"CAM-05 GREEN PARK · 2026-03-14 22:14:{10 + (i//25):02d} UTC", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 229, 255), 2)
        out.write(frame)

    out.release()
    print(f"Generated realistic footage at: {dest_path}")

def run():
    ingestion = VideoIngestionService()
    cv_service = CVProcessingService()

    case_ref = "CASE-2026-001"
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        c_row = conn.execute("SELECT case_id FROM cases WHERE case_ref = %s", (case_ref,)).fetchone()
        case_id = c_row["case_id"]
        cam_row = conn.execute("SELECT camera_id FROM cctv_cameras WHERE case_id = %s AND ref = 'CAM-05'", (case_id,)).fetchone()
        camera_id = cam_row["camera_id"] if cam_row else None

    storage_dir = os.path.join(ingestion.storage_root, case_ref)
    os.makedirs(storage_dir, exist_ok=True)
    video_filename = "CAM05_GreenPark_2214UTC_Footage.mp4"
    dest_path = os.path.join(storage_dir, video_filename)

    generate_demo_footage(dest_path)
    meta = ingestion.extract_metadata(dest_path)

    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        v_row = conn.execute("""
            INSERT INTO cctv_videos (
                case_id, camera_id, filename, file_path, file_size_bytes,
                sha256_hash, duration_sec, fps, total_frames, width, height, mime_type, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'video/mp4', 'UPLOADED')
            ON CONFLICT (case_id, video_id) DO NOTHING
            RETURNING video_id
        """, (
            case_id, camera_id, video_filename, dest_path,
            meta["file_size_bytes"], meta["sha256_hash"],
            meta["duration_sec"], meta["fps"], meta["total_frames"],
            meta["width"], meta["height"]
        )).fetchone()
        video_id = v_row["video_id"]

        job_row = conn.execute("""
            INSERT INTO cv_processing_jobs (case_id, video_id, status)
            VALUES (%s, %s, 'QUEUED')
            RETURNING job_id
        """, (case_id, video_id)).fetchone()
        job_id = job_row["job_id"]
        conn.commit()

    print(f"Dispatching real CV pipeline: Job #{job_id}, Video #{video_id}...")
    cv_service.run_pipeline_sync(
        job_id=job_id,
        case_id=case_id,
        video_id=video_id,
        video_path=dest_path,
        case_ref=case_ref,
        model_name="yolo11n.pt",
        tracker_type="bytetrack",
        confidence_thresh=0.25,
        iou_thresh=0.45,
        frame_skip=1
    )
    print("DEMO CCTV REAL CV PIPELINE EXECUTED!")

if __name__ == "__main__":
    run()
