"""CCTV Computer Vision Endpoints.
Provides REST APIs for video ingestion, YOLO model inference,
ByteTrack tracking, event timelines, and EVLM evidence queries.
"""

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from .. import db
from ..cv.schemas import (
    CameraCreate,
    ProcessVideoRequest,
)
from ..cv.service import CVProcessingService
from ..cv.video_ingestion import VideoIngestionService
from ..deps import Ctx, get_ctx, load_case

router = APIRouter(prefix="/api/cctv", tags=["cctv"])
ingestion_service = VideoIngestionService()
cv_service = CVProcessingService()


# -------------------------------------------------------------------------
# Cameras Management
# -------------------------------------------------------------------------
@router.get("/cameras")
def list_cameras(case: str = Query(...), ctx: Ctx = Depends(get_ctx)):
    case_row = load_case(ctx, case)
    rows = ctx.conn.execute(
        """
        SELECT camera_id, case_id, ref, name, resolution, fps, coverage_zone, is_active, created_at
        FROM cctv_cameras
        WHERE case_id = %s
        ORDER BY ref ASC
        """,
        (case_row["case_id"],),
    ).fetchall()
    return rows


@router.post("/cameras")
def create_camera(
    data: CameraCreate,
    case: str = Query(...),
    ctx: Ctx = Depends(get_ctx),
):
    case_row = load_case(ctx, case)
    row = ctx.conn.execute(
        """
        INSERT INTO cctv_cameras (case_id, ref, name, resolution, fps, coverage_zone, rtsp_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING camera_id, ref, name
        """,
        (
            case_row["case_id"],
            data.ref,
            data.name,
            data.resolution,
            data.fps,
            data.coverage_zone,
            data.rtsp_url,
        ),
    ).fetchone()
    ctx.conn.commit()
    return row


# -------------------------------------------------------------------------
# Video Ingestion & Metadata
# -------------------------------------------------------------------------
@router.post("/videos/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    case: str = Form(...),
    camera_id: Optional[int] = Form(None),
    auto_process: bool = Form(False),
    file: UploadFile = File(...),
    ctx: Ctx = Depends(get_ctx),
):
    case_row = load_case(ctx, case)
    case_id = case_row["case_id"]

    # Save to disk
    dest_path = ingestion_service.save_upload(case, file.filename, file.file)

    # Validate and extract metadata
    try:
        meta = ingestion_service.extract_metadata(dest_path)
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(status_code=400, detail=f"Failed to process video metadata: {e}")

    row = ctx.conn.execute(
        """
        INSERT INTO cctv_videos (
            case_id, camera_id, filename, file_path, file_size_bytes,
            sha256_hash, duration_sec, fps, total_frames, width, height, mime_type, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'UPLOADED')
        RETURNING video_id, filename, file_size_bytes, sha256_hash, duration_sec, fps, total_frames, width, height, status
        """,
        (
            case_id,
            camera_id,
            file.filename,
            dest_path,
            meta["file_size_bytes"],
            meta["sha256_hash"],
            meta["duration_sec"],
            meta["fps"],
            meta["total_frames"],
            meta["width"],
            meta["height"],
            file.content_type or "video/mp4",
        ),
    ).fetchone()

    video_id = row["video_id"]
    ctx.conn.commit()

    # If auto-processing requested, initialize job
    job_id = None
    if auto_process:
        job_row = ctx.conn.execute(
            """
            INSERT INTO cv_processing_jobs (case_id, video_id, status)
            VALUES (%s, %s, 'QUEUED')
            RETURNING job_id
            """,
            (case_id, video_id),
        ).fetchone()
        job_id = job_row["job_id"]
        ctx.conn.commit()
        background_tasks.add_task(
            cv_service.run_pipeline_sync,
            job_id,
            case_id,
            video_id,
            dest_path,
            case,
        )

    return {
        "video": row,
        "job_id": job_id,
        "message": "Footage uploaded successfully" + (" and queued for CV inference" if auto_process else ""),
    }


@router.get("/videos")
def list_videos(case: str = Query(...), ctx: Ctx = Depends(get_ctx)):
    case_row = load_case(ctx, case)
    rows = ctx.conn.execute(
        """
        SELECT v.*, c.ref as camera_ref, c.name as camera_name
        FROM cctv_videos v
        LEFT JOIN cctv_cameras c ON v.camera_id = c.camera_id
        WHERE v.case_id = %s
        ORDER BY v.created_at DESC
        """,
        (case_row["case_id"],),
    ).fetchall()
    return rows


@router.get("/videos/{video_id}")
def get_video(video_id: int, ctx: Ctx = Depends(get_ctx)):
    row = ctx.conn.execute(
        """
        SELECT v.*, c.ref as camera_ref, c.name as camera_name
        FROM cctv_videos v
        LEFT JOIN cctv_cameras c ON v.camera_id = c.camera_id
        WHERE v.video_id = %s
        """,
        (video_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return row


# -------------------------------------------------------------------------
# Processing Jobs & YOLO Execution
# -------------------------------------------------------------------------
@router.post("/videos/{video_id}/process")
def process_video(
    video_id: int,
    req: ProcessVideoRequest,
    background_tasks: BackgroundTasks,
    ctx: Ctx = Depends(get_ctx),
):
    v_row = ctx.conn.execute(
        "SELECT v.*, c.case_ref FROM cctv_videos v JOIN cases c ON v.case_id = c.case_id WHERE v.video_id = %s",
        (video_id,),
    ).fetchone()
    if not v_row:
        raise HTTPException(status_code=404, detail="Video not found")

    job_row = ctx.conn.execute(
        """
        INSERT INTO cv_processing_jobs (
            case_id, video_id, model_name, tracker_type,
            confidence_thresh, iou_thresh, frame_skip, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'QUEUED')
        RETURNING job_id
        """,
        (
            v_row["case_id"],
            video_id,
            req.model_name,
            req.tracker_type,
            req.confidence_thresh,
            req.iou_thresh,
            req.frame_skip,
        ),
    ).fetchone()
    job_id = job_row["job_id"]
    ctx.conn.commit()

    background_tasks.add_task(
        cv_service.run_pipeline_sync,
        job_id,
        v_row["case_id"],
        video_id,
        v_row["file_path"],
        v_row["case_ref"],
        req.model_name,
        req.tracker_type,
        req.confidence_thresh,
        req.iou_thresh,
        req.frame_skip,
    )

    return {"job_id": job_id, "status": "QUEUED", "message": "Inference job dispatched to background worker"}


@router.get("/jobs/{job_id}")
def get_job_status(job_id: int, ctx: Ctx = Depends(get_ctx)):
    row = ctx.conn.execute(
        "SELECT * FROM cv_processing_jobs WHERE job_id = %s",
        (job_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row


# -------------------------------------------------------------------------
# Detections, Tracks, and Events
# -------------------------------------------------------------------------
@router.get("/videos/{video_id}/detections")
def get_video_detections(
    video_id: int,
    frame_number: Optional[int] = None,
    class_name: Optional[str] = None,
    limit: int = 500,
    ctx: Ctx = Depends(get_ctx),
):
    q = "SELECT * FROM cv_detections WHERE video_id = %s"
    params: List[Any] = [video_id]

    if frame_number is not None:
        q += " AND frame_number = %s"
        params.append(frame_number)
    if class_name:
        q += " AND class_name = %s"
        params.append(class_name.lower())

    q += " ORDER BY frame_number ASC, confidence DESC LIMIT %s"
    params.append(limit)

    rows = ctx.conn.execute(q, tuple(params)).fetchall()
    return rows


@router.get("/videos/{video_id}/tracks")
def get_video_tracks(video_id: int, ctx: Ctx = Depends(get_ctx)):
    rows = ctx.conn.execute(
        """
        SELECT track_id, class_name, first_seen_sec, last_seen_sec, duration_sec, total_frames, max_confidence, trajectory
        FROM cv_tracks
        WHERE video_id = %s
        ORDER BY first_seen_sec ASC
        """,
        (video_id,),
    ).fetchall()
    return rows


@router.get("/videos/{video_id}/events")
def get_video_events(video_id: int, ctx: Ctx = Depends(get_ctx)):
    rows = ctx.conn.execute(
        """
        SELECT e.*, ev.ref as evidence_ref, ev.validity_status as evidence_validity
        FROM cctv_events e
        LEFT JOIN evidence ev ON e.evidence_id = ev.evidence_id
        WHERE e.video_id = %s
        ORDER BY e.start_sec ASC
        """,
        (video_id,),
    ).fetchall()
    return rows


@router.get("/events/{event_id}")
def get_event_details(event_id: int, ctx: Ctx = Depends(get_ctx)):
    row = ctx.conn.execute(
        """
        SELECT e.*, ev.ref as evidence_ref, ev.validity_status as evidence_validity,
               v.filename as video_filename, c.ref as camera_ref
        FROM cctv_events e
        JOIN cctv_videos v ON e.video_id = v.video_id
        LEFT JOIN cctv_cameras c ON e.camera_id = c.camera_id
        LEFT JOIN evidence ev ON e.evidence_id = ev.evidence_id
        WHERE e.event_id = %s
        """,
        (event_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Event not found")
    return row


# -------------------------------------------------------------------------
# Case-wide Timeline & Multimodal Correlations
# -------------------------------------------------------------------------
@router.get("/cases/{case_ref}/timeline")
def get_case_cctv_timeline(case_ref: str, ctx: Ctx = Depends(get_ctx)):
    case_row = load_case(ctx, case_ref)
    rows = ctx.conn.execute(
        """
        SELECT e.*, v.filename as video_filename, c.ref as camera_ref, c.name as camera_name
        FROM cctv_events e
        JOIN cctv_videos v ON e.video_id = v.video_id
        LEFT JOIN cctv_cameras c ON e.camera_id = c.camera_id
        WHERE e.case_id = %s
        ORDER BY e.start_sec ASC
        """,
        (case_row["case_id"],),
    ).fetchall()
    return rows


@router.get("/cases/{case_ref}/correlations")
def get_case_cctv_correlations(case_ref: str, ctx: Ctx = Depends(get_ctx)):
    case_row = load_case(ctx, case_ref)
    rows = ctx.conn.execute(
        """
        SELECT * FROM cctv_event_correlations
        WHERE case_id = %s
        ORDER BY created_at DESC
        """,
        (case_row["case_id"],),
    ).fetchall()
    return rows


# -------------------------------------------------------------------------
# Static File & Video Streaming Handlers
# -------------------------------------------------------------------------
@router.get("/artifacts/{case_ref}/{filename}")
def serve_cctv_artifact(case_ref: str, filename: str):
    storage_root = os.path.join(os.path.dirname(__file__), "..", "..", "storage", "evidence", case_ref)
    target = os.path.join(storage_root, filename)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail="Evidence frame artifact not found")
    return FileResponse(target, media_type="image/jpeg")


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: int):
    with db.connection() as conn:
        row = conn.execute(
            """
            SELECT v.file_path, v.mime_type, v.filename, c.case_ref
            FROM cctv_videos v
            JOIN cases c ON v.case_id = c.case_id
            WHERE v.video_id = %s
            """,
            (video_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Video record not found")

        fpath = row["file_path"]
        if not os.path.isabs(fpath):
            fpath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", fpath))

        if not os.path.exists(fpath):
            # Check fallback in case directory
            case_ref = row["case_ref"]
            fname = row["filename"]
            alt_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "storage", "cctv", case_ref, fname)
            )
            if os.path.exists(alt_path):
                fpath = alt_path
            else:
                raise HTTPException(status_code=404, detail=f"Video file '{fname}' not found on server disk")

        return FileResponse(
            fpath,
            media_type=row.get("mime_type") or "video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "public, max-age=3600",
            },
        )
