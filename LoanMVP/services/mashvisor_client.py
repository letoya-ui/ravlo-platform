import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


class MashvisorError(Exception):
    pass


@dataclass
class MashvisorConfig:
    api_key: str
    base_url: str = "https://api.mashvisor.com/v1.1/client"
    timeout_seconds: int = 20


class MashvisorClient:
    def __init__(self, config: Optional[MashvisorConfig] = None) -> None:
        if config is None:
            api_key = os.getenv("MASHVISOR_API_KEY", "").strip()
            base_url = os.getenv(
                "MASHVISOR_BASE_URL",
                "https://api.mashvisor.com/v1.1/client"
            ).strip()

            if not api_key:
                raise MashvisorError("Missing MASHVISOR_API_KEY in environment.")

            config = MashvisorConfig(api_key=api_key, base_url=base_url)

        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": self.config.api_key,
            "Accept": "application/json",
            "User-Agent": "Ravlo/1.0",
        })

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.config.base_url}/{endpoint}"

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        clean_params: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if value is not None and value != "":
                clean_params[key] = value

        url = self._build_url(endpoint)

        try:
            response = self.session.get(
                url,
                params=clean_params,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise MashvisorError(f"Network error calling Mashvisor: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise MashvisorError(
                f"Mashvisor returned non-JSON response: {response.text[:500]}"
            ) from exc

        if not response.ok:
            raise MashvisorError(
                f"Mashvisor error {response.status_code}: {data}"
            )

        return data

    def get_property_by_address(
        self,
        *,
        address: str,
        city: str,
        state: str,
        zip_code: str,
    ) -> Dict[str, Any]:
        return self._get(
            "property",
            params={
                "address": address,
                "city": city,
                "state": state,
                "zip_code": zip_code,
            },
        )

    def get_property_images(self, property_id: Any) -> Dict[str, Any]:
        """
        Fetch listing images for a Mashvisor property.

        Returns:
        {
            "status": "success" | "error",
            "property_id": <id>,
            "photos": [<url>, ...],
            "primary_photo": <url or None>,
            "raw": <raw response>,
            "message": <optional error message>
        }
        """
        if not property_id:
            return {
                "status": "error",
                "property_id": property_id,
                "photos": [],
                "primary_photo": None,
                "raw": {},
                "message": "property_id is required",
            }

        try:
            data = self._get(f"property/{property_id}/images")
        except Exception as e:
            return {
                "status": "error",
                "property_id": property_id,
                "photos": [],
                "primary_photo": None,
                "raw": {},
                "message": str(e),
            }

        content = data.get("content") if isinstance(data, dict) else {}
        if not isinstance(content, dict):
            content = {}

        photos = []

        def _push(url: Any) -> None:
            if not url:
                return
            clean = str(url).strip()
            if not clean:
                return
            if clean not in photos:
                photos.append(clean)

        image_block = content.get("image")
        if isinstance(image_block, dict):
            _push(image_block.get("url"))
            _push(image_block.get("image"))
        elif isinstance(image_block, str):
            _push(image_block)

        extra_images = content.get("extra_images")
        if isinstance(extra_images, list):
            for img in extra_images:
                if isinstance(img, str):
                    _push(img)
                elif isinstance(img, dict):
                    _push(img.get("url"))
                    _push(img.get("image"))

        photos_block = content.get("photos")
        if isinstance(photos_block, list):
            for img in photos_block:
                if isinstance(img, str):
                    _push(img)
                elif isinstance(img, dict):
                    _push(img.get("url"))
                    _push(img.get("image"))

        primary_photo = photos[0] if photos else None

        return {
            "status": "success",
            "property_id": property_id,
            "photos": photos,
            "primary_photo": primary_photo,
            "raw": data,
        }

    def get_airbnb_lookup(
        self,
        *,
        address: str,
        city: str,
        state: str,
        zip_code: str,
        beds: Optional[int] = None,
        baths: Optional[float] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> Dict[str, Any]:
        return self._get(
            "rento-calculator/lookup",
            params={
                "address": address,
                "city": city,
                "state": state,
                "zip_code": zip_code,
                "beds": beds,
                "baths": baths,
                "lat": lat,
                "lng": lng,
                "resource": "airbnb",
            },
        )

    def get_airbnb_comps(
        self,
        *,
        state: str,
        zip_code: str,
    ) -> Dict[str, Any]:
        return self._get(
            "rento-calculator/export-comps",
            params={
                "state": state,
                "zip_code": zip_code,
                "resource": "airbnb",
            },
        )

    def validate_property_with_mashvisor(
        self,
        *,
        address: str,
        city: str,
        state: str,
        zip_code: str,
        beds: Optional[int] = None,
        baths: Optional[float] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        include_comps: bool = False,
    ) -> Dict[str, Any]:
        """
        Recommended flow:
        - call only after property + strategy are selected
        - default to property + lookup
        - only fetch comps when truly needed, to reduce usage
        """
        result: Dict[str, Any] = {
            "property": None,
            "lookup": None,
            "comps": None,
            "errors": [],
        }

        try:
            result["property"] = self.get_property_by_address(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
            )
        except MashvisorError as exc:
            result["errors"].append({"property": str(exc)})

        try:
            result["lookup"] = self.get_airbnb_lookup(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                beds=beds,
                baths=baths,
                lat=lat,
                lng=lng,
            )
        except MashvisorError as exc:
            result["errors"].append({"lookup": str(exc)})

        if include_comps:
            try:
                result["comps"] = self.get_airbnb_comps(
                    state=state,
                    zip_code=zip_code,
                )
            except MashvisorError as exc:
                result["errors"].append({"comps": str(exc)})

        return result