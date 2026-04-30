import base64
import copy
import json
import os
import traceback
from datetime import datetime

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user, login_required
from openai import OpenAI
from werkzeug.exceptions import NotFound

from LoanMVP.extensions import csrf, db
from LoanMVP.models.borrowers import Deal
from LoanMVP.models.renovation_models import BuildProject
from LoanMVP.services.investor.investor_media_helpers import _upload_build_images_from_b64
from LoanMVP.services.investor.investor_project_studio_helpers import (
    _deal_results,
    _set_deal_results,
)
from LoanMVP.utils.decorators import role_required


generator_build_bp = Blueprint(
    "generator_build",
    __name__,
    url_prefix="/api/generator/build",
)

investor_generator_build_bp = Blueprint(
    "investor_generator_build",
    __name__,
    url_prefix="/investor/api/generator/build",
)


def _build_chat_prompt(messages, current_spec=None):
    current_spec = current_spec or {}

    return f"""
You are Ravlo Build Studio.

Help the user create a clear build specification before generation.

Return ONLY valid JSON in this shape:

{{
  "status": "needs_more_info" or "ready",
  "assistant_message": "Natural language response to the user.",
  "spec": {{
    "intent": "",
    "property_type": "",
    "style": "",
    "preserve_layout": true,
    "blueprint_url": "",
    "reference_image_url": "",
    "exterior_view": "front",
    "finish_level": "",
    "stories": "",
    "roof_style": "",
    "siding_material": "",
    "window_style": "",
    "special_features": "",
    "notes": ""
  }},
  "missing_fields": [],
  "next_questions": []
}}

Current spec:
{current_spec}

Conversation:
{messages}
""".strip()


def _safe_json(text):
    import json

    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()

    try:
        return json.loads(text)
    except Exception:
        return {
            "status": "needs_more_info",
            "assistant_message": text or "I need a little more information before generating.",
            "spec": {},
            "missing_fields": [],
            "next_questions": [],
        }


def _post_build_generate(engine_url, spec):
    session = requests.Session()
    session.trust_env = False
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    api_key = (
        current_app.config.get("RENOVATION_API_KEY")
        or current_app.config.get("RENOVATION_ENGINE_API_KEY")
        or os.getenv("RENOVATION_API_KEY")
        or os.getenv("RENOVATION_ENGINE_API_KEY")
        or ""
    ).strip()
    if api_key:
        headers["X-API-Key"] = api_key

    return session.post(
        f"{engine_url}/api/generator/build/generate",
        json={"spec": spec},
        headers=headers,
        timeout=600,
        verify=_engine_verify_ssl(),
    )


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _safe_object_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _request_data_and_spec():
    if request.files or request.form:
        data = request.form.to_dict(flat=True)
        spec = _safe_object_json(data.get("spec"))
        if not spec:
            spec = {}

        for key, value in data.items():
            if key in {"csrf_token", "spec"}:
                continue
            if value not in (None, ""):
                spec.setdefault(key, value)

        file_key_map = {
            "blueprint_file": ("blueprint_image_base64", "blueprint_image_filename"),
            "blueprint_image": ("blueprint_image_base64", "blueprint_image_filename"),
            "floor_plan_file": ("blueprint_image_base64", "blueprint_image_filename"),
            "land_image": ("reference_image_base64", "reference_image_filename"),
            "reference_image": ("reference_image_base64", "reference_image_filename"),
            "site_image": ("site_image_base64", "site_image_filename"),
            "exterior_image": ("exterior_image_base64", "exterior_image_filename"),
        }

        for form_key, (payload_key, filename_key) in file_key_map.items():
            upload = request.files.get(form_key)
            if not upload or not getattr(upload, "filename", ""):
                continue
            raw = upload.read()
            if not raw:
                continue

            encoded = base64.b64encode(raw).decode("utf-8")
            spec[payload_key] = encoded
            spec[filename_key] = upload.filename

            if form_key == "land_image":
                spec.setdefault("site_image_base64", encoded)
                spec.setdefault("exterior_image_base64", encoded)
            if form_key in {"reference_image", "site_image", "exterior_image"}:
                spec.setdefault("reference_image_base64", encoded)

        return data, spec

    data = request.get_json(silent=True) or {}
    spec = _as_dict(data.get("spec") or data)
    return data, spec


def _normalize_int(value):
    try:
        if value in (None, ""):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _truthy(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on", "save")


def _engine_verify_ssl():
    verify_ssl = current_app.config.get("RENOVATION_ENGINE_VERIFY_SSL")
    if verify_ssl is None:
        verify_ssl = os.getenv("RENOVATION_ENGINE_VERIFY_SSL")
    if verify_ssl is not None:
        return _truthy(verify_ssl, default=True)

    insecure_ssl = current_app.config.get("RENOVATION_ENGINE_INSECURE_SSL")
    if insecure_ssl is None:
        insecure_ssl = os.getenv("RENOVATION_ENGINE_INSECURE_SSL")
    return not _truthy(insecure_ssl, default=False)


def _first_nonempty(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if value:
                return value
        elif value:
            return value
    return ""


def _find_first_url(value):
    if isinstance(value, str):
        value = value.strip()
        if value.startswith(("http://", "https://", "/static/", "uploads/", "static/")):
            return value
        return ""

    if isinstance(value, list):
        for item in value:
            found = _find_first_url(item)
            if found:
                return found
        return ""

    if isinstance(value, dict):
        for key in (
            "image_url",
            "blueprint_url",
            "render_url",
            "concept_render_url",
            "exterior_url",
            "public_url",
            "cdn_url",
            "url",
            "src",
        ):
            found = _find_first_url(value.get(key))
            if found:
                return found

        for key in (
            "images",
            "image_urls",
            "outputs",
            "result",
            "build",
            "blueprint",
            "exterior",
            "concept",
        ):
            found = _find_first_url(value.get(key))
            if found:
                return found

    return ""


def _find_urls(value, limit=8):
    urls = []
    seen = set()

    def collect(item):
        if len(urls) >= limit:
            return
        if isinstance(item, str):
            url = _find_first_url(item)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
            return
        if isinstance(item, list):
            for nested in item:
                collect(nested)
            return
        if isinstance(item, dict):
            for key in (
                "image_url",
                "blueprint_url",
                "render_url",
                "concept_render_url",
                "exterior_url",
                "public_url",
                "cdn_url",
                "url",
                "src",
            ):
                collect(item.get(key))
            for key in (
                "images",
                "image_urls",
                "outputs",
                "result",
                "build",
                "blueprint",
                "exterior",
                "concept",
            ):
                collect(item.get(key))

    collect(value)
    return urls


def _ensure_generator_image_urls(payload):
    payload = _as_dict(payload)
    image_urls = _find_urls(payload)

    if image_urls:
        payload.setdefault("image_url", image_urls[0])
        payload.setdefault("images", image_urls)
        return image_urls

    images_b64 = payload.get("images_base64") or payload.get("image_base64_list") or []
    if isinstance(images_b64, str):
        images_b64 = [images_b64]

    if images_b64:
        uploaded = _upload_build_images_from_b64(
            images_b64,
            prefix=f"build-generator/{datetime.utcnow().strftime('%Y%m%d')}",
        )
        if uploaded:
            payload["image_url"] = uploaded[0]
            payload["images"] = uploaded
            return uploaded

    return []


def _candidate_payload_blocks(payload):
    payload = _as_dict(payload)
    blocks = []
    queue = [payload]
    keys = (
        "result",
        "build",
        "build_project",
        "outputs",
        "output",
        "package",
        "data",
        "project",
    )

    while queue:
        block = queue.pop(0)
        if not isinstance(block, dict) or block in blocks:
            continue
        blocks.append(block)
        for key in keys:
            value = block.get(key)
            if isinstance(value, dict):
                queue.append(value)
    return blocks


def _find_named_output(payload, keys):
    keys = tuple(keys)
    for block in _candidate_payload_blocks(payload):
        for key in keys:
            value = block.get(key)
            if value not in (None, "", [], {}):
                return value

    normalized_keys = []
    for key in keys:
        words = [
            word
            for word in str(key).lower().replace("-", "_").split("_")
            if word and word != "result"
        ]
        if words:
            normalized_keys.append(words)
    normalized_keys.sort(key=len, reverse=True)
    generic_singletons = {"blueprint", "exterior", "interior", "concept", "render", "plan"}

    for block in _candidate_payload_blocks(payload):
        for collection_key in ("outputs", "images", "image_outputs", "results"):
            for item in _as_list(block.get(collection_key)):
                if not isinstance(item, dict):
                    continue
                label = " ".join(
                    str(item.get(label_key) or "")
                    for label_key in ("type", "mode", "key", "name", "label", "view", "output_type")
                ).lower()
                label_key = label.replace("-", "_").replace(" ", "_")
                if not label_key:
                    continue
                for words in normalized_keys:
                    if len(words) == 1 and words[0] in generic_singletons:
                        continue
                    if all(word in label_key for word in words):
                        return item

    return {}


def _coerce_output_block(value):
    if isinstance(value, str):
        url = _find_first_url(value)
        return {"image_url": url, "images": [url]} if url else {}

    if isinstance(value, list):
        urls = _find_urls(value)
        if urls:
            return {"image_url": urls[0], "images": urls}
        for item in value:
            block = _coerce_output_block(item)
            if block:
                return block
        return {}

    if isinstance(value, dict):
        block = _compact_engine_response(value)
        urls = _find_urls(block)
        if urls:
            block.setdefault("image_url", urls[0])
            block.setdefault("images", urls)
        return block

    return {}


def _normalize_generator_outputs(payload):
    aliases = {
        "blueprint": (
            "blueprint_result",
            "blueprint",
            "blueprint_floor1",
            "first_floor_blueprint",
            "floor_plan",
            "floor_plan_result",
            "plan",
        ),
        "blueprint_floor2": (
            "blueprint_floor2_result",
            "blueprint_floor2",
            "second_floor_blueprint",
            "floor2_blueprint",
            "second_floor",
            "site_plan",
        ),
        "blueprint_floor3": (
            "blueprint_floor3_result",
            "blueprint_floor3",
            "third_floor_blueprint",
            "floor3_blueprint",
            "third_floor",
        ),
        "exterior": (
            "exterior_result",
            "exterior",
            "exterior_front",
            "front_exterior",
            "concept",
            "render",
        ),
        "exterior_back": (
            "exterior_back_result",
            "exterior_back",
            "exterior_rear",
            "rear_exterior",
            "back_exterior",
        ),
        "interior": (
            "interior_result",
            "interior",
            "room_result",
            "design_result",
        ),
    }

    outputs = {}
    for output_key, names in aliases.items():
        block = _coerce_output_block(_find_named_output(payload, names))
        if block and _find_first_url(block):
            outputs[output_key] = block

    if not outputs:
        urls = _find_urls(payload)
        if urls:
            fallback = {"image_url": urls[0], "images": urls}
            outputs["blueprint"] = fallback
            outputs["exterior"] = fallback

    return outputs


def _merge_output_record(existing, generated, *, values, image_url="", source="generator_build", **extra):
    record = dict(_as_dict(existing))
    generated = _as_dict(generated)
    record.update(_compact_engine_response(generated))
    record.update({
        "project_name": values.get("project_name"),
        "property_type": values.get("property_type"),
        "development_type": values.get("development_type"),
        "style": values.get("style"),
        "stories": values.get("stories"),
        "description": values.get("description"),
        "lot_size": values.get("lot_size"),
        "zoning": values.get("zoning"),
        "location": values.get("location"),
        "notes": values.get("notes"),
        "source": source,
    })
    record.update({key: value for key, value in extra.items() if value not in (None, "")})

    resolved_url = _first_nonempty(image_url, _find_first_url(generated), record.get("image_url"))
    if resolved_url:
        record["image_url"] = resolved_url
        urls = _find_urls(generated)
        if not urls:
            urls = [resolved_url]
        record["images"] = urls

    return {key: value for key, value in record.items() if value not in (None, "", [], {})}


def _compact_engine_response(payload):
    def scrub(value):
        if isinstance(value, dict):
            cleaned = {}
            for key, nested in value.items():
                key_text = str(key).lower()
                if "base64" in key_text or key_text in {"b64", "raw_image", "image_bytes"}:
                    continue
                cleaned[key] = scrub(nested)
            return cleaned
        if isinstance(value, list):
            return [scrub(item) for item in value[:20]]
        if isinstance(value, str) and len(value) > 2000:
            return value[:2000]
        return value

    return scrub(copy.deepcopy(payload))


def _investor_context_from_request(data, spec):
    deal_id = _normalize_int(
        data.get("deal_id")
        or spec.get("deal_id")
        or data.get("investor_deal_id")
        or spec.get("investor_deal_id")
    )
    project_id = _normalize_int(
        data.get("project_id")
        or spec.get("project_id")
        or data.get("build_project_id")
        or spec.get("build_project_id")
    )

    deal = None
    if deal_id:
        deal = Deal.query.filter_by(id=deal_id, user_id=current_user.id).first()
        if not deal:
            raise NotFound("Deal not found or not authorized.")

    project = None
    if project_id:
        project = BuildProject.query.filter_by(id=project_id, user_id=current_user.id).first()
        if not project:
            raise NotFound("Build project not found or not authorized.")

    if not project and deal is not None:
        results = _deal_results(deal)
        existing_project_id = _normalize_int(
            _as_dict(results.get("build_project")).get("project_id")
        )
        if existing_project_id:
            project = BuildProject.query.filter_by(
                id=existing_project_id,
                user_id=current_user.id,
            ).first()

    return deal, project


def _build_project_values(spec, payload, deal=None):
    build_block = _as_dict(payload.get("build") or payload.get("result") or payload)
    location = _first_nonempty(
        spec.get("location"),
        spec.get("address"),
        build_block.get("location"),
        build_block.get("address"),
        getattr(deal, "address", None),
    )
    return {
        "project_name": _first_nonempty(
            spec.get("project_name"),
            spec.get("name"),
            build_block.get("project_name"),
            build_block.get("name"),
            getattr(deal, "title", None),
            "Generated Build",
        ),
        "property_type": _first_nonempty(
            spec.get("property_type"),
            build_block.get("property_type"),
            "single_family",
        ),
        "development_type": _first_nonempty(
            spec.get("development_type"),
            build_block.get("development_type"),
            spec.get("intent"),
            "Generated Build",
        ),
        "description": _first_nonempty(
            spec.get("build_description"),
            spec.get("description"),
            build_block.get("build_description"),
            build_block.get("description"),
            spec.get("notes"),
        ),
        "lot_size": _first_nonempty(spec.get("lot_size"), build_block.get("lot_size")),
        "zoning": _first_nonempty(spec.get("zoning"), build_block.get("zoning")),
        "location": location,
        "notes": _first_nonempty(
            spec.get("notes"),
            spec.get("special_features"),
            build_block.get("notes"),
            build_block.get("special_features"),
        ),
        "style": _first_nonempty(spec.get("style"), build_block.get("style")),
        "stories": _first_nonempty(
            spec.get("stories"),
            spec.get("number_of_floors"),
            spec.get("floor_count"),
            build_block.get("stories"),
            build_block.get("number_of_floors"),
        ),
    }


def _save_investor_generator_build(data, spec, payload):
    if not getattr(current_user, "is_authenticated", False):
        return {}

    deal, project = _investor_context_from_request(data, spec)
    output_urls = _ensure_generator_image_urls(payload)
    outputs = _normalize_generator_outputs(payload)

    blueprint_block = outputs.get("blueprint", {})
    blueprint_floor2_block = outputs.get("blueprint_floor2", {})
    blueprint_floor3_block = outputs.get("blueprint_floor3", {})
    exterior_block = outputs.get("exterior", {})
    exterior_back_block = outputs.get("exterior_back", {})
    interior_block = outputs.get("interior", {})

    primary_url = _first_nonempty(
        _find_first_url(exterior_block),
        _find_first_url(blueprint_block),
        output_urls[0] if output_urls else "",
        _find_first_url(payload),
    )
    blueprint_url = _first_nonempty(
        spec.get("blueprint_url"),
        _find_first_url(blueprint_block),
        _find_first_url(_as_dict(payload).get("blueprint")),
        _find_first_url(_as_dict(payload).get("floor_plan")),
        primary_url,
    )
    blueprint_floor2_url = _first_nonempty(
        _find_first_url(blueprint_floor2_block),
        _find_first_url(_as_dict(payload).get("blueprint_floor2")),
        _find_first_url(_as_dict(payload).get("site_plan")),
    )
    exterior_url = _first_nonempty(
        _find_first_url(exterior_block),
        _find_first_url(_as_dict(payload).get("exterior")),
        _find_first_url(_as_dict(payload).get("concept")),
        primary_url,
    )
    exterior_back_url = _find_first_url(exterior_back_block)
    interior_url = _find_first_url(interior_block)

    values = _build_project_values(spec, payload, deal=deal)

    if project is None:
        project = BuildProject(user_id=current_user.id)
        db.session.add(project)

    project.project_name = values["project_name"]
    project.property_type = values["property_type"]
    project.development_type = values["development_type"]
    project.description = values["description"]
    project.lot_size = values["lot_size"]
    project.zoning = values["zoning"]
    project.location = values["location"]
    project.notes = values["notes"]
    if blueprint_url:
        project.blueprint_url = blueprint_url
    if blueprint_floor2_url:
        project.site_plan_url = blueprint_floor2_url
    if exterior_url:
        project.concept_render_url = exterior_url
        project.exterior_url = exterior_url

    db.session.flush()

    if deal is not None:
        results = _deal_results(deal)
        build_project = _as_dict(results.get("build_project"))
        generator_result = {
            "project_id": project.id,
            "project_name": values["project_name"],
            "property_type": values["property_type"],
            "development_type": values["development_type"],
            "style": values["style"],
            "stories": values["stories"],
            "description": values["description"],
            "lot_size": values["lot_size"],
            "zoning": values["zoning"],
            "location": values["location"],
            "notes": values["notes"],
            "image_url": primary_url,
            "images": output_urls,
            "outputs": copy.deepcopy(outputs),
            "spec": copy.deepcopy(spec),
            "engine_response": _compact_engine_response(payload),
            "saved_at": datetime.utcnow().isoformat(),
            "source": "generator_build",
        }

        build_project.update({
            "project_id": project.id,
            "project_name": values["project_name"],
            "property_type": values["property_type"],
            "development_type": values["development_type"],
            "style": values["style"],
            "stories": values["stories"],
            "description": values["description"],
            "lot_size": values["lot_size"],
            "zoning": values["zoning"],
            "location": values["location"],
            "notes": values["notes"],
            "latest_generator_build": generator_result,
        })

        if blueprint_url:
            build_project["blueprint"] = _merge_output_record(
                build_project.get("blueprint"),
                blueprint_block,
                values=values,
                image_url=blueprint_url,
                blueprint_url=blueprint_url,
            )

        if blueprint_floor2_url:
            build_project["blueprint_floor2"] = _merge_output_record(
                build_project.get("blueprint_floor2") or build_project.get("site_plan"),
                blueprint_floor2_block,
                values=values,
                image_url=blueprint_floor2_url,
                blueprint_url=blueprint_floor2_url,
                floor_label="Second Floor",
                blueprint_floor="second",
            )

        if _find_first_url(blueprint_floor3_block):
            build_project["blueprint_floor3"] = _merge_output_record(
                build_project.get("blueprint_floor3"),
                blueprint_floor3_block,
                values=values,
                image_url=_find_first_url(blueprint_floor3_block),
                blueprint_url=_find_first_url(blueprint_floor3_block),
                floor_label="Third Floor",
                blueprint_floor="third",
            )

        if exterior_url:
            build_project["exterior"] = _merge_output_record(
                build_project.get("exterior"),
                exterior_block,
                values=values,
                image_url=exterior_url,
                view="front",
            )

        if exterior_back_url:
            build_project["exterior_back"] = _merge_output_record(
                build_project.get("exterior_back"),
                exterior_back_block,
                values=values,
                image_url=exterior_back_url,
                view="back",
            )

        if interior_url:
            existing_interior = _as_dict(build_project.get("interior"))
            room_entry = _merge_output_record(
                existing_interior.get("latest"),
                interior_block,
                values=values,
                image_url=interior_url,
                room_type=spec.get("room_type") or _as_dict(interior_block).get("room_type"),
                floor=spec.get("floor") or _as_dict(interior_block).get("floor"),
            )
            rooms = [
                room for room in _as_list(existing_interior.get("rooms"))
                if isinstance(room, dict) and room.get("image_url") != room_entry.get("image_url")
            ]
            rooms.append(room_entry)
            existing_interior["latest"] = room_entry
            existing_interior["rooms"] = rooms
            build_project["interior"] = existing_interior

        results["build_project"] = build_project
        _set_deal_results(deal, results)

    db.session.commit()

    build_studio_url = (
        url_for("investor.build_studio", deal_id=deal.id)
        if deal is not None
        else url_for("investor.build_studio", project_id=project.id)
    )
    deal_architect_url = (
        url_for("investor.deal_architect", deal_id=deal.id, project_id=project.id)
        if deal is not None
        else None
    )
    budget_studio_url = (
        url_for("investor.budget_studio", deal_id=deal.id)
        if deal is not None
        else None
    )

    return {
        "saved": True,
        "deal_id": deal.id if deal else None,
        "project_id": project.id,
        "image_url": primary_url,
        "outputs": outputs,
        "blueprint_result": outputs.get("blueprint", {}),
        "blueprint_floor2_result": outputs.get("blueprint_floor2", {}),
        "blueprint_floor3_result": outputs.get("blueprint_floor3", {}),
        "exterior_result": outputs.get("exterior", {}),
        "exterior_back_result": outputs.get("exterior_back", {}),
        "interior_result": outputs.get("interior", {}),
        "build_studio_url": build_studio_url,
        "deal_architect_url": deal_architect_url,
        "budget_studio_url": budget_studio_url,
        "next_url": build_studio_url,
    }


def _build_chat_response():
    data = request.get_json(silent=True) or {}
    messages = data.get("messages") or []
    current_spec = data.get("spec") or {}

    client = OpenAI(api_key=current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model=current_app.config.get("AI_MODEL") or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Ravlo Build Studio. Return only valid JSON."},
            {"role": "user", "content": _build_chat_prompt(messages, current_spec)},
        ],
        temperature=0.25,
    )

    return jsonify(_safe_json(response.choices[0].message.content))


def _build_generate_response(*, persist_to_investor=False):
    data, spec = _request_data_and_spec()

    engine_url = (
        current_app.config.get("RENOVATION_ENGINE_URL")
        or os.getenv("RENOVATION_ENGINE_URL")
        or ""
    ).rstrip("/")

    current_app.logger.info("FORWARDING BUILD GENERATOR TO RENOVATION_ENGINE_URL=%s", engine_url)

    if not engine_url:
        return jsonify(
            {
                "status": "error",
                "message": "RENOVATION_ENGINE_URL is not configured.",
            }
        ), 500

    try:
        response = _post_build_generate(engine_url, spec)
    except requests.exceptions.SSLError as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
                "detail": (
                    "The HTTPS request reached the network but TLS failed before "
                    "certificate verification. For ngrok dev URLs this usually "
                    "means local network security is blocking the tunnel hostname."
                ),
            }
        ), 502
    except requests.exceptions.RequestException as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502

    try:
        raw_payload = response.json()
        payload = raw_payload if isinstance(raw_payload, dict) else {
            "status": "ok",
            "result": raw_payload,
        }
    except Exception:
        payload = {
            "status": "error",
            "message": response.text,
        }

    if persist_to_investor and response.ok and _as_dict(payload).get("status") not in ("error", "failed"):
        save_enabled = _truthy(
            data.get("save_to_investor")
            if "save_to_investor" in data
            else data.get("save_to_deal"),
            default=True,
        )
        if save_enabled:
            try:
                save_context = _save_investor_generator_build(data, spec, payload)
                if save_context:
                    payload.setdefault("investor", save_context)
                    payload.setdefault("project_id", save_context.get("project_id"))
                    payload.setdefault("deal_id", save_context.get("deal_id"))
                    payload.setdefault("next_url", save_context.get("next_url"))
                    payload.setdefault("build_studio_url", save_context.get("build_studio_url"))
                    payload.setdefault("deal_architect_url", save_context.get("deal_architect_url"))
                    payload.setdefault("budget_studio_url", save_context.get("budget_studio_url"))
                    payload.setdefault("outputs", save_context.get("outputs"))
                    payload.setdefault("blueprint_result", save_context.get("blueprint_result"))
                    payload.setdefault("blueprint_floor2_result", save_context.get("blueprint_floor2_result"))
                    payload.setdefault("blueprint_floor3_result", save_context.get("blueprint_floor3_result"))
                    payload.setdefault("exterior_result", save_context.get("exterior_result"))
                    payload.setdefault("exterior_back_result", save_context.get("exterior_back_result"))
                    payload.setdefault("interior_result", save_context.get("interior_result"))
            except NotFound as exc:
                db.session.rollback()
                return jsonify({"status": "error", "message": exc.description}), 404
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception("Investor build generator save failed")
                payload.setdefault("investor", {
                    "saved": False,
                    "error": str(exc),
                })

    payload.setdefault("status", "ok")
    return jsonify(payload), response.status_code


@generator_build_bp.post("/chat")
@csrf.exempt
def build_chat():
    try:
        return _build_chat_response()

    except Exception as exc:
        traceback.print_exc()
        return jsonify(
            {
                "status": "error",
                "assistant_message": str(exc),
                "spec": {},
                "missing_fields": [],
                "next_questions": [],
            }
        ), 500


@generator_build_bp.post("/generate")
@csrf.exempt
def build_generate():
    try:
        return _build_generate_response()

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(exc)}), 500


@investor_generator_build_bp.post("/chat")
@login_required
@role_required("investor")
def investor_build_chat():
    try:
        return _build_chat_response()
    except Exception as exc:
        traceback.print_exc()
        return jsonify(
            {
                "status": "error",
                "assistant_message": str(exc),
                "spec": {},
                "missing_fields": [],
                "next_questions": [],
            }
        ), 500


@investor_generator_build_bp.post("/generate")
@login_required
@role_required("investor")
def investor_build_generate():
    try:
        return _build_generate_response(persist_to_investor=True)
    except Exception as exc:
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"status": "error", "message": str(exc)}), 500
