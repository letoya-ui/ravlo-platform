"""Training data collection and Replicate fine-tuning integration.

Studio (SDXL LoRA):
  - Logs every image generation to StudioGenerationLog
  - Exports approved images as ZIP for Replicate training
  - Triggers SDXL LoRA training job via Replicate API

Academy (LLM fine-tune):
  - Logs every Academy chat exchange to AcademyChatLog
  - Exports approved pairs as JSONL (OpenAI fine-tune format)
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Replicate config
# ---------------------------------------------------------------------------

REPLICATE_API_KEY = os.environ.get("REPLICATE_API_KEY", "")

# The Replicate SDXL LoRA trainer version — update to latest when available.
# https://replicate.com/stability-ai/sdxl
REPLICATE_SDXL_TRAINER = os.environ.get(
    "REPLICATE_SDXL_TRAINER_VERSION",
    "stability-ai/sdxl",
)
REPLICATE_SDXL_DESTINATION = os.environ.get(
    "REPLICATE_SDXL_DESTINATION",
    "ravlo/ravlo-studio-sdxl",
)


# ---------------------------------------------------------------------------
# Studio generation logging
# ---------------------------------------------------------------------------

def log_studio_generation(
    feature: str,
    provider: str,
    output_mode: str,
    prompt: str,
    payload: dict,
    image_url: str,
    user_id: Optional[int] = None,
) -> None:
    """Persist one StudioGenerationLog row. Never raises — called fire-and-forget."""
    try:
        from LoanMVP.extensions import db
        from LoanMVP.models.training_models import StudioGenerationLog

        entry = StudioGenerationLog(
            user_id=user_id,
            feature=feature,
            provider=provider,
            output_mode=output_mode,
            prompt=prompt[:2000] if prompt else None,
            payload_json=json.dumps(payload, default=str)[:8000] if payload else None,
            image_url=image_url,
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:
        log.warning("log_studio_generation failed (non-fatal): %s", exc)


def log_studio_batch(
    feature: str,
    provider: str,
    payload: dict,
    images_b64_or_urls: dict,          # {output_mode: url_or_b64}
    user_id: Optional[int] = None,
    is_urls: bool = True,
) -> None:
    """Log a multi-output generation batch (one row per output mode)."""
    for mode, value in (images_b64_or_urls or {}).items():
        if not value:
            continue
        prompt = payload.get("prompt") or payload.get("description") or ""
        url = value if is_urls else ""
        log_studio_generation(
            feature=feature,
            provider=provider,
            output_mode=mode,
            prompt=prompt,
            payload=payload,
            image_url=url,
            user_id=user_id,
        )


# ---------------------------------------------------------------------------
# Academy chat logging
# ---------------------------------------------------------------------------

def log_academy_chat(
    messages: list,
    ai_response: str,
    tier: Optional[str] = None,
    feature: str = "chat",
    system_prompt: str = "",
    model: str = "",
    user_id: Optional[int] = None,
    session_key: Optional[str] = None,
) -> Optional[int]:
    """Persist one AcademyChatLog row. Returns the new row id, or None on error."""
    try:
        from LoanMVP.extensions import db
        from LoanMVP.models.training_models import AcademyChatLog

        entry = AcademyChatLog(
            user_id=user_id,
            session_key=session_key,
            tier=tier,
            feature=feature,
            system_prompt=system_prompt[:2000] if system_prompt else None,
            messages_json=json.dumps(messages, default=str)[:16000],
            ai_response=ai_response[:8000] if ai_response else None,
            model=model,
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
        return entry.id
    except Exception as exc:
        log.warning("log_academy_chat failed (non-fatal): %s", exc)
        return None


# ---------------------------------------------------------------------------
# Studio training data export (ZIP)
# ---------------------------------------------------------------------------

def export_studio_training_zip(approved_only: bool = True) -> io.BytesIO:
    """Build a ZIP of studio training images + captions.txt for Replicate.

    Each approved StudioGenerationLog with an image_url is downloaded and
    added to the ZIP. A captions.txt file lists ``filename: prompt`` pairs
    in the format expected by the SDXL LoRA trainer.

    Returns a BytesIO containing the ZIP bytes.
    """
    import requests as http
    from LoanMVP.models.training_models import StudioGenerationLog

    query = StudioGenerationLog.query
    if approved_only:
        query = query.filter_by(approved_for_training=True)
    rows = query.order_by(StudioGenerationLog.id.asc()).all()

    buf = io.BytesIO()
    captions = []

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            if not row.image_url:
                continue
            try:
                resp = http.get(row.image_url, timeout=15)
                resp.raise_for_status()
                ext = "webp" if "webp" in (resp.headers.get("Content-Type") or "") else "png"
                fname = f"{row.id}_{row.output_mode or 'image'}.{ext}"
                zf.writestr(fname, resp.content)
                prompt = (row.prompt or "").strip() or f"ravlo {row.output_mode} architectural render"
                captions.append(f"{fname}: {prompt}")
                log.debug("Added %s to training ZIP", fname)
            except Exception as exc:
                log.warning("Skipping image %s in training export: %s", row.image_url, exc)

        if captions:
            zf.writestr("captions.txt", "\n".join(captions))

    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Academy training data export (JSONL)
# ---------------------------------------------------------------------------

def export_academy_training_jsonl(approved_only: bool = True) -> io.BytesIO:
    """Export Academy chat logs as JSONL in OpenAI fine-tune format.

    Each row produces one JSONL line:
      {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
    """
    from LoanMVP.models.training_models import AcademyChatLog

    query = AcademyChatLog.query
    if approved_only:
        query = query.filter_by(approved_for_training=True)
    rows = query.order_by(AcademyChatLog.id.asc()).all()

    lines = []
    for row in rows:
        try:
            messages = json.loads(row.messages_json or "[]")
            if not messages or not row.ai_response:
                continue

            system = row.system_prompt or (
                "You are Ravlo Academy, an expert AI coach for real estate investors and professionals."
            )
            convo = [{"role": "system", "content": system}]
            convo.extend(messages)
            convo.append({"role": "assistant", "content": row.ai_response})
            lines.append(json.dumps({"messages": convo}))
        except Exception as exc:
            log.warning("Skipping AcademyChatLog %s in export: %s", row.id, exc)

    buf = io.BytesIO(("\n".join(lines) + "\n").encode("utf-8"))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Replicate SDXL LoRA training trigger
# ---------------------------------------------------------------------------

def trigger_sdxl_lora_training(
    zip_url: str,
    token: str = "RAVLORENDER",
    steps: int = 1000,
    lora_lr: float = 0.0001,
    triggered_by_user_id: Optional[int] = None,
) -> dict:
    """Submit an SDXL LoRA training job to Replicate.

    ``zip_url`` must be a publicly accessible URL to a ZIP of training images.
    Returns the created TrainingJob record as a dict.
    """
    if not REPLICATE_API_KEY:
        raise RuntimeError("REPLICATE_API_KEY is not set.")

    import requests as http
    from LoanMVP.extensions import db
    from LoanMVP.models.training_models import TrainingJob

    config = {
        "input_images": zip_url,
        "token_string": token,
        "caption_prefix": f"a photo of {token}",
        "max_train_steps": steps,
        "lora_lr": lora_lr,
        "batch_size": 1,
        "resolution": 1024,
        "use_face_detection_instead": False,
    }

    job = TrainingJob(
        job_type="sdxl_lora",
        provider="replicate",
        config_json=json.dumps(config),
        status="pending",
        triggered_by=triggered_by_user_id,
        created_at=datetime.utcnow(),
    )
    db.session.add(job)
    db.session.flush()

    try:
        resp = http.post(
            f"https://api.replicate.com/v1/models/{REPLICATE_SDXL_DESTINATION}/versions",
            headers={
                "Authorization": f"Token {REPLICATE_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "version": REPLICATE_SDXL_TRAINER,
                "input": config,
                "destination": REPLICATE_SDXL_DESTINATION,
            },
            timeout=30,
        )
        data = resp.json()
        job.external_job_id = data.get("id") or data.get("urls", {}).get("get", "")
        job.result_json = json.dumps(data)
        job.status = "running" if resp.ok else "failed"
    except Exception as exc:
        log.error("Replicate training trigger failed: %s", exc)
        job.status = "failed"
        job.result_json = json.dumps({"error": str(exc)})

    db.session.commit()
    return {
        "id": job.id,
        "external_job_id": job.external_job_id,
        "status": job.status,
    }


def check_training_job_status(job_id: int) -> dict:
    """Poll Replicate for the current status of a training job."""
    import requests as http
    from LoanMVP.extensions import db
    from LoanMVP.models.training_models import TrainingJob

    job = TrainingJob.query.get(job_id)
    if not job:
        return {"error": "Job not found"}

    if not job.external_job_id or not REPLICATE_API_KEY:
        return {"id": job_id, "status": job.status}

    try:
        resp = http.get(
            f"https://api.replicate.com/v1/trainings/{job.external_job_id}",
            headers={"Authorization": f"Token {REPLICATE_API_KEY}"},
            timeout=15,
        )
        data = resp.json()
        replicate_status = data.get("status", job.status)

        status_map = {
            "starting": "running",
            "processing": "running",
            "succeeded": "succeeded",
            "failed": "failed",
            "canceled": "canceled",
        }
        job.status = status_map.get(replicate_status, job.status)
        job.result_json = json.dumps(data)

        if job.status == "succeeded":
            job.model_url = (data.get("output") or {}).get("weights") or data.get("output_url")
            job.completed_at = datetime.utcnow()

        db.session.commit()
    except Exception as exc:
        log.warning("check_training_job_status failed: %s", exc)

    return {
        "id": job.id,
        "external_job_id": job.external_job_id,
        "status": job.status,
        "model_url": job.model_url,
    }
