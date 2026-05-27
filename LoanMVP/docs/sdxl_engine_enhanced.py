import asyncio
import gc
import json
import os
import time
import uuid
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from config import DEVICE
from engines.pipeline_loader import load_pipeline
from utils.logging_utils import log
from generator.shared.runtime import _token_count, encode_prompts, _clip_safe_text

# ---------------------------------------------------------------------------
# Training data collection
# ---------------------------------------------------------------------------

_TRAINING_DIR = Path(os.environ.get("TRAINING_DATA_DIR", "training_data"))
_TRAINING_LOG = _TRAINING_DIR / "generation_log.jsonl"
_TRAINING_IMAGES_DIR = _TRAINING_DIR / "images"
_COLLECT_TRAINING_DATA = os.environ.get("COLLECT_TRAINING_DATA", "1") not in ("0", "false", "no")
_MAX_TRAINING_IMAGES = int(os.environ.get("MAX_TRAINING_IMAGES", "5000"))


def _ensure_training_dirs():
    _TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    _TRAINING_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def _count_training_images() -> int:
    try:
        return sum(1 for _ in _TRAINING_IMAGES_DIR.glob("*.png"))
    except Exception:
        return 0


def _save_training_sample(prompt: str, negative: str, image: Image.Image, req, seed: int, pipe_mode: str):
    """Persist a successful generation as a training pair (image + JSONL metadata)."""
    if not _COLLECT_TRAINING_DATA:
        return

    try:
        if _count_training_images() >= _MAX_TRAINING_IMAGES:
            return

        _ensure_training_dirs()

        sample_id = uuid.uuid4().hex
        img_filename = f"{sample_id}.png"
        img_path = _TRAINING_IMAGES_DIR / img_filename
        image.save(str(img_path), format="PNG")

        record = {
            "id": sample_id,
            "image_file": img_filename,
            "prompt": prompt,
            "negative_prompt": negative,
            "seed": seed,
            "pipe_mode": pipe_mode,
            "steps": getattr(req, "steps", None),
            "guidance": getattr(req, "guidance", None),
            "strength": getattr(req, "strength", None),
            "mode": getattr(req, "mode", None),
            "task": getattr(req, "task", None),
            "family": getattr(req, "generation_family", None),
            "studio": getattr(req, "studio", None),
            "room_type": getattr(req, "room_type", None),
            "style": getattr(req, "style", None),
            "property_type": getattr(req, "property_type", None),
            "timestamp": time.time(),
            "approved": False,
            "quality_rating": None,
        }

        with open(str(_TRAINING_LOG), "a") as f:
            f.write(json.dumps(record) + "\n")

    except Exception as exc:
        log.warning("[training] save_training_sample failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# LoRA weight loading
# ---------------------------------------------------------------------------

_LORA_DIR = Path(os.environ.get("LORA_WEIGHTS_DIR", "lora_weights"))
_LORA_SCALE = float(os.environ.get("LORA_SCALE", "0.85"))
_lora_applied_pipes: set = set()  # track which pipe objects already have LoRA loaded


def _find_latest_lora() -> Path | None:
    """Return the most recently modified LoRA weights file in _LORA_DIR, or None."""
    if not _LORA_DIR.exists():
        return None
    candidates = sorted(
        list(_LORA_DIR.glob("*.safetensors")) + list(_LORA_DIR.glob("*.bin")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _apply_lora_if_available(pipe, pipe_mode: str):
    """Attach the latest LoRA weights to a pipeline (once per pipeline object)."""
    pipe_id = id(pipe)
    if pipe_id in _lora_applied_pipes:
        return

    lora_path = _find_latest_lora()
    if lora_path is None:
        return

    try:
        pipe.load_lora_weights(str(lora_path))
        if hasattr(pipe, "set_adapters"):
            pipe.set_adapters(["default"], adapter_weights=[_LORA_SCALE])
        elif hasattr(pipe, "fuse_lora"):
            pipe.fuse_lora(lora_scale=_LORA_SCALE)

        _lora_applied_pipes.add(pipe_id)
        log.info(
            "[lora] Applied LoRA weights from %s (scale=%.2f) to %s pipe_mode=%s",
            lora_path.name, _LORA_SCALE, pipe.__class__.__name__, pipe_mode,
        )
    except Exception as exc:
        log.warning("[lora] Failed to apply LoRA weights (non-fatal): %s", exc)


def reload_lora():
    """Force LoRA to be re-applied on the next generation (call after deploying new weights)."""
    _lora_applied_pipes.clear()
    log.info("[lora] LoRA cache cleared — weights will reload on next generation.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Imported lazily to avoid circular import at module load time.
def _get_encode_prompts():
    from generator.shared.runtime import encode_prompts, _token_count
    return encode_prompts, _token_count


def cleanup_cuda():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def _valid_images(out):
    if out is None:
        return None

    imgs = getattr(out, "images", None)
    if not imgs or len(imgs) == 0:
        return None

    clean = []
    for im in imgs:
        if im is None:
            continue

        try:
            extrema = im.getextrema()
            if isinstance(extrema, tuple) and all(channel == (0, 0) for channel in extrema):
                continue
            clean.append(im)
        except Exception:
            continue

    return clean or None


def _make_generator(seed=None):
    seed = seed or int(time.time()) % 2_147_483_647
    if str(DEVICE).startswith("cuda") and torch.cuda.is_available():
        return torch.Generator(device="cuda").manual_seed(seed), seed
    return torch.Generator().manual_seed(seed), seed


def _run_pipe_call(local_pipe, **kwargs):
    if str(DEVICE).startswith("cuda") and torch.cuda.is_available():
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.float16):
            return local_pipe(**kwargs)

    with torch.inference_mode():
        return local_pipe(**kwargs)


def _is_img2img_pipe(local_pipe) -> bool:
    return "img2img" in local_pipe.__class__.__name__.lower()


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

async def generate_with_sdxl(req, prompt, negative, init_img, depth_img, canny_img):
    generator, used_seed = _make_generator(getattr(req, "seed", None))

    def _truthy(value) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def _clip_safe_text_local(value, max_words=170, max_chars=1400):
        text = str(value or "").strip()
        if not text:
            return ""

        words = text.split()
        if len(words) > max_words:
            text = " ".join(words[:max_words])

        if len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0].strip()

        return text

    family = str(
        getattr(req, "generation_family", None)
        or getattr(req, "generator_family", None)
        or getattr(req, "generator_type", None)
        or ""
    ).lower()

    studio = str(
        getattr(req, "studio", None)
        or getattr(req, "studio_type", None)
        or ""
    ).lower()

    mode = str(getattr(req, "mode", "") or "").lower()
    task = str(getattr(req, "task", "") or "").lower()
    design_mode = str(getattr(req, "design_mode", "") or "").lower()
    reference_role = str(getattr(req, "reference_role", "") or "").lower()
    layout_lock = _truthy(getattr(req, "layout_lock", False))

    is_overlay = (
        task == "design_overlay"
        or design_mode == "overlay"
        or reference_role == "layout_locked_reference"
        or layout_lock
    )

    is_design = (
        family == "design"
        or studio == "design_studio"
        or "design" in task
    )

    is_interior = (
        mode == "interior"
        or bool(getattr(req, "room_type", None))
        or "interior" in task
        or is_overlay
    )

    controlnet_scale = float(
        getattr(req, "controlnet_scale", 0.55 if is_overlay else 0.8)
        or (0.55 if is_overlay else 0.8)
    )

    if is_design and is_interior:
        default_strength = 0.72 if is_overlay else 0.76
        min_strength = 0.72 if is_overlay else 0.50

        steps = min(max(int(getattr(req, "steps", 34) or 34), 24), 40)
        guidance = min(max(float(getattr(req, "guidance", 9.6) or 9.6), 6.0), 11.0)
        strength = min(
            max(
                float(getattr(req, "strength", default_strength) or default_strength),
                min_strength,
            ),
            0.92,
        )
    else:
        steps = int(getattr(req, "steps", 20) or 20)
        guidance = float(getattr(req, "guidance", 7.0) or 7.0)
        strength = float(getattr(req, "strength", 0.75) or 0.75)

    try:
        setattr(req, "steps", steps)
        setattr(req, "guidance", guidance)
        setattr(req, "strength", strength)
    except Exception:
        pass

    print(
        "[generate_with_sdxl]",
        "family=", family,
        "studio=", studio,
        "mode=", mode,
        "task=", task,
        "design_mode=", design_mode,
        "reference_role=", reference_role,
        "layout_lock=", layout_lock,
        "is_overlay=", is_overlay,
        "is_design=", is_design,
        "is_interior=", bool(is_interior),
        "steps=", steps,
        "guidance=", guidance,
        "strength=", strength,
        "controlnet_scale=", controlnet_scale,
        flush=True,
    )

    count = 1

    req_use_depth = _truthy(getattr(req, "use_depth", False))
    req_use_canny = _truthy(getattr(req, "use_canny", False))

    print(
        "[sdxl-control-flags]",
        "req.use_depth=", getattr(req, "use_depth", None),
        "req.use_canny=", getattr(req, "use_canny", None),
        "req_use_depth=", req_use_depth,
        "req_use_canny=", req_use_canny,
        "depth_img=", depth_img is not None,
        "canny_img=", canny_img is not None,
        flush=True,
    )

    attempts = []

    if req_use_depth and req_use_canny and depth_img is not None and canny_img is not None:
        attempts.append({
            "label": "dual_control",
            "pipe_mode": "dual",
            "use_depth": True,
            "use_canny": True,
        })

    if req_use_depth and depth_img is not None:
        attempts.append({
            "label": "depth_only",
            "pipe_mode": "depth",
            "use_depth": True,
            "use_canny": False,
        })

    attempts.append({
        "label": "no_control",
        "pipe_mode": "base",
        "use_depth": False,
        "use_canny": False,
    })

    print(
        "[sdxl-attempt-plan]",
        [
            {
                "label": attempt["label"],
                "pipe_mode": attempt["pipe_mode"],
                "use_depth": attempt["use_depth"],
                "use_canny": attempt["use_canny"],
            }
            for attempt in attempts
        ],
        flush=True,
    )

    last_error = None

    safe_prompt = _clip_safe_text_local(prompt, max_words=60, max_chars=520)
    safe_negative = _clip_safe_text_local(negative, max_words=55, max_chars=420)

    for attempt_index, attempt in enumerate(attempts, start=1):
        pipe_mode = attempt["pipe_mode"]

        try:
            pipe = load_pipeline(pipe_mode)
            if pipe is None:
                raise RuntimeError(f"Failed to load SDXL pipeline for mode={pipe_mode}")

            # Inject LoRA weights if available (skipped on subsequent calls to same pipe)
            _apply_lora_if_available(pipe, pipe_mode)

            pipe_name = pipe.__class__.__name__.lower()
            is_img2img = "img2img" in pipe_name

            kwargs = {
                "prompt": safe_prompt,
                "negative_prompt": safe_negative,
                "num_inference_steps": steps,
                "guidance_scale": guidance,
                "generator": generator,
                "num_images_per_prompt": count,
            }

            if pipe_mode == "dual":
                kwargs["image"] = init_img
                kwargs["control_image"] = [depth_img, canny_img]
                kwargs["strength"] = strength
                kwargs["controlnet_conditioning_scale"] = [
                    controlnet_scale,
                    min(controlnet_scale, 0.35),
                ]

            elif pipe_mode == "depth":

                rear_mode = (
                    str(getattr(req, "render_family", "") or "").lower() == "rear_exterior"
                    or str(getattr(req, "generation_mode", "") or "").lower() == "rear_from_front_style_anchor"
                )

                if not rear_mode:
                    kwargs["image"] = init_img

                kwargs["control_image"] = depth_img
                kwargs["strength"] = strength
                kwargs["controlnet_conditioning_scale"] = controlnet_scale

            elif pipe_mode == "canny":
                kwargs["image"] = init_img
                kwargs["control_image"] = canny_img
                kwargs["strength"] = strength
                kwargs["controlnet_conditioning_scale"] = min(controlnet_scale, 0.35)

            else:
                # Base may be text-to-image or img2img. Text-to-image must not receive image kwargs.
                kwargs.pop("image", None)
                kwargs.pop("control_image", None)
                kwargs.pop("strength", None)
                kwargs.pop("controlnet_conditioning_scale", None)

                if is_img2img and init_img is not None:
                    kwargs["image"] = init_img
                    kwargs["strength"] = strength
                else:
                    kwargs["width"] = int(getattr(req, "width", 1024) or 1024)
                    kwargs["height"] = int(getattr(req, "height", 1024) or 1024)

            print(
                "[sdxl_attempt_start]",
                "attempt=", attempt_index,
                "label=", attempt["label"],
                "seed=", used_seed,
                "pipe_mode=", pipe_mode,
                "pipe_class=", pipe.__class__.__name__,
                "has_init_img=", init_img is not None,
                "has_depth_img=", depth_img is not None,
                "has_canny_img=", canny_img is not None,
                "prompt_tokens=", len(safe_prompt.split()),
                "negative_tokens=", len(safe_negative.split()),
                "kwargs=", sorted(kwargs.keys()),
                flush=True,
            )

            out = _run_pipe_call(pipe, **kwargs)
            images = _valid_images(out)

            if not images:
                raise RuntimeError(f"SDXL returned no valid images for pipe_mode={pipe_mode}")

            print(
                "[sdxl_attempt_success]",
                "attempt=", attempt_index,
                "label=", attempt["label"],
                "count=", len(images),
                flush=True,
            )

            # Collect training data from the first (best) image
            _save_training_sample(
                prompt=safe_prompt,
                negative=safe_negative,
                image=images[0],
                req=req,
                seed=used_seed,
                pipe_mode=pipe_mode,
            )

            return images, used_seed

        except Exception as exc:
            last_error = exc
            print(
                "[sdxl_attempt_failed]",
                "attempt=", attempt_index,
                "label=", attempt["label"],
                "pipe_mode=", pipe_mode,
                "error=", str(exc),
                flush=True,
            )
            cleanup_cuda()
            continue

    raise RuntimeError(f"SDXL generation failed: {last_error}")
