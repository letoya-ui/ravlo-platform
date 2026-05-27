"""Admin routes for training data management and Replicate job triggering.

Prefix: /training
All routes require admin access.

Routes
------
GET  /training/dashboard          – overview of collected data + active jobs
POST /training/studio/rate/<id>   – rate a studio generation 1-5
POST /training/studio/approve/<id>– toggle approved_for_training on studio log
POST /training/academy/rate/<id>  – thumbs up/down on academy chat log
POST /training/academy/approve/<id>– toggle approved_for_training on academy log
GET  /training/export/studio      – download approved studio images as ZIP
GET  /training/export/academy     – download approved academy chats as JSONL
POST /training/trigger/studio     – submit SDXL LoRA job to Replicate
GET  /training/jobs/<id>/status   – poll Replicate for job status
"""

from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    send_file,
)
from flask_login import current_user, login_required

from LoanMVP.utils.decorators import role_required
from LoanMVP.extensions import db
from LoanMVP.models.training_models import (
    AcademyChatLog,
    StudioGenerationLog,
    TrainingJob,
)
from LoanMVP.services.training_service import (
    check_training_job_status,
    export_academy_training_jsonl,
    export_studio_training_zip,
    trigger_sdxl_lora_training,
)

training_bp = Blueprint("training", __name__, url_prefix="/training")


def _admin_only():
    """Return 403 JSON if caller is not an admin; None if allowed."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required."}), 401
    role = getattr(current_user, "role", None)
    if role not in ("admin", "admin_group", "executive"):
        return jsonify({"error": "Admin access required."}), 403
    return None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@training_bp.get("/dashboard")
@login_required
def dashboard():
    guard = _admin_only()
    if guard:
        return guard

    studio_total = StudioGenerationLog.query.count()
    studio_approved = StudioGenerationLog.query.filter_by(approved_for_training=True).count()
    studio_rated = StudioGenerationLog.query.filter(StudioGenerationLog.quality_rating.isnot(None)).count()

    academy_total = AcademyChatLog.query.count()
    academy_approved = AcademyChatLog.query.filter_by(approved_for_training=True).count()
    academy_rated = AcademyChatLog.query.filter(AcademyChatLog.thumbs_up.isnot(None)).count()

    jobs = (
        TrainingJob.query
        .order_by(TrainingJob.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "studio": {
            "total": studio_total,
            "approved": studio_approved,
            "rated": studio_rated,
        },
        "academy": {
            "total": academy_total,
            "approved": academy_approved,
            "rated": academy_rated,
        },
        "recent_jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "provider": j.provider,
                "status": j.status,
                "sample_count": j.sample_count,
                "model_url": j.model_url,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ],
    })


# ---------------------------------------------------------------------------
# Studio rating + approval
# ---------------------------------------------------------------------------

@training_bp.post("/studio/rate/<int:log_id>")
@login_required
def rate_studio(log_id: int):
    guard = _admin_only()
    if guard:
        return guard

    row = StudioGenerationLog.query.get_or_404(log_id)
    rating = request.get_json(silent=True, force=True) or {}
    score = rating.get("rating")

    if score is None or not (1 <= int(score) <= 5):
        return jsonify({"error": "rating must be 1–5"}), 400

    row.quality_rating = int(score)
    if int(score) >= 4:
        row.approved_for_training = True

    db.session.commit()
    return jsonify({"id": log_id, "rating": row.quality_rating, "approved": row.approved_for_training})


@training_bp.post("/studio/approve/<int:log_id>")
@login_required
def approve_studio(log_id: int):
    guard = _admin_only()
    if guard:
        return guard

    row = StudioGenerationLog.query.get_or_404(log_id)
    row.approved_for_training = not row.approved_for_training
    db.session.commit()
    return jsonify({"id": log_id, "approved": row.approved_for_training})


# ---------------------------------------------------------------------------
# Academy rating + approval
# ---------------------------------------------------------------------------

@training_bp.post("/academy/rate/<int:log_id>")
@login_required
def rate_academy(log_id: int):
    guard = _admin_only()
    if guard:
        return guard

    row = AcademyChatLog.query.get_or_404(log_id)
    body = request.get_json(silent=True, force=True) or {}
    thumbs = body.get("thumbs_up")

    if thumbs is None:
        return jsonify({"error": "thumbs_up (bool) is required"}), 400

    row.thumbs_up = bool(thumbs)
    if row.thumbs_up:
        row.approved_for_training = True

    db.session.commit()
    return jsonify({"id": log_id, "thumbs_up": row.thumbs_up, "approved": row.approved_for_training})


@training_bp.post("/academy/approve/<int:log_id>")
@login_required
def approve_academy(log_id: int):
    guard = _admin_only()
    if guard:
        return guard

    row = AcademyChatLog.query.get_or_404(log_id)
    row.approved_for_training = not row.approved_for_training
    db.session.commit()
    return jsonify({"id": log_id, "approved": row.approved_for_training})


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

@training_bp.get("/export/studio")
@login_required
def export_studio():
    guard = _admin_only()
    if guard:
        return guard

    approved_only = request.args.get("all") != "1"
    buf = export_studio_training_zip(approved_only=approved_only)
    filename = f"ravlo_studio_training_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=filename)


@training_bp.get("/export/academy")
@login_required
def export_academy():
    guard = _admin_only()
    if guard:
        return guard

    approved_only = request.args.get("all") != "1"
    buf = export_academy_training_jsonl(approved_only=approved_only)
    filename = f"ravlo_academy_training_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.jsonl"
    return send_file(buf, mimetype="application/jsonl", as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# Replicate training trigger
# ---------------------------------------------------------------------------

@training_bp.post("/trigger/studio")
@login_required
def trigger_studio():
    """Start an SDXL LoRA training job on Replicate.

    Expects JSON body:
      {
        "zip_url":  "https://...",   # publicly accessible ZIP of training images
        "token":    "RAVLORENDER",   # optional trigger token
        "steps":    1000,            # optional
        "lora_lr":  0.0001           # optional
      }

    Alternatively, pass ?auto=1 to build the ZIP from approved studio logs
    and upload it to Spaces before triggering (requires Spaces config).
    """
    guard = _admin_only()
    if guard:
        return guard

    body = request.get_json(silent=True, force=True) or {}
    zip_url = (body.get("zip_url") or "").strip()

    if not zip_url and request.args.get("auto") == "1":
        zip_url = _auto_upload_studio_zip()

    if not zip_url:
        return jsonify({
            "error": "Provide zip_url in the request body, or use ?auto=1 to build from approved logs."
        }), 400

    approved_count = StudioGenerationLog.query.filter_by(approved_for_training=True).count()

    result = trigger_sdxl_lora_training(
        zip_url=zip_url,
        token=body.get("token", "RAVLORENDER"),
        steps=int(body.get("steps", 1000)),
        lora_lr=float(body.get("lora_lr", 0.0001)),
        triggered_by_user_id=current_user.id,
    )

    job = TrainingJob.query.get(result["id"])
    if job:
        job.sample_count = approved_count
        db.session.commit()

    return jsonify(result), 202 if result.get("status") == "running" else 200


def _auto_upload_studio_zip() -> str:
    """Build the training ZIP from approved studio logs and upload to Spaces."""
    try:
        from LoanMVP.services.investor.investor_media_helpers import (
            _get_spaces_client,
            SPACES_BUCKET,
            _public_spaces_url,
        )
        client = _get_spaces_client()
        buf = export_studio_training_zip(approved_only=True)
        key = f"training/studio_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
        client.put_object(
            Bucket=SPACES_BUCKET,
            Key=key,
            Body=buf.read(),
            ACL="public-read",
            ContentType="application/zip",
        )
        return _public_spaces_url(key)
    except Exception as exc:
        current_app.logger.error("Auto ZIP upload failed: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Job status
# ---------------------------------------------------------------------------

@training_bp.get("/jobs/<int:job_id>/status")
@login_required
def job_status(job_id: int):
    guard = _admin_only()
    if guard:
        return guard

    result = check_training_job_status(job_id)
    return jsonify(result)
