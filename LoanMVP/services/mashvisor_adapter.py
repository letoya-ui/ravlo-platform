from typing import Any, Dict

from LoanMVP.services.mashvisor_client import MashvisorClient, MashvisorError
from LoanMVP.services.mashvisor_service import normalize_mashvisor_validation


class MashvisorAdapter:
    def __init__(self) -> None:
        try:
            self.client = MashvisorClient()
        except Exception:
            self.client = None

    def enabled(self) -> bool:
        return self.client is not None

    def validate_property(
        self,
        *,
        address: str,
        city: str,
        state: str,
        zip_code: str,
        beds=None,
        baths=None,
        lat=None,
        lng=None,
        include_comps: bool = False,
    ) -> Dict[str, Any]:
        if not self.enabled():
            return {}

        try:
            result = self.client.validate_property_with_mashvisor(
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                beds=beds,
                baths=baths,
                lat=lat,
                lng=lng,
                include_comps=include_comps,
            )
            return normalize_mashvisor_validation(result)
        except MashvisorError:
            return {}
        except Exception:
            return {}