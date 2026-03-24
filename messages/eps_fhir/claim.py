import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from uuid import uuid4

from messages.eps_fhir.common_maps import (
    ERD_DEFAULT_REPEATS_ALLOWED,
    ERD_DEFAULT_REPEATS_ISSUED,
)

DEFAULT_DISPENSER_USER_ID = "555260695103"
DEFAULT_DISPENSER_ROLE_ID = "555265434108"


class Claim:
    def __init__(self, context: Any) -> None:
        self.context = context
        self.claim_payload = self._load_template()
        self._patch_dynamic_values()
        self.body = json.dumps(self.claim_payload)

    def _load_template(self) -> dict:
        template_path = Path(__file__).resolve().parents[1] / "examples" / "claim" / "request.json"
        with open(template_path, encoding="utf-8") as template_file:
            return json.load(template_file)

    def _patch_dynamic_values(self) -> None:
        self.claim_payload["id"] = str(uuid4())
        self.claim_payload["created"] = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        self.claim_payload["identifier"][0]["value"] = str(uuid4())

        dispenser_user_id = getattr(self.context, "dispenser_user_id", DEFAULT_DISPENSER_USER_ID)
        dispenser_role_id = getattr(self.context, "dispenser_role_id", DEFAULT_DISPENSER_ROLE_ID)

        self.claim_payload["extension"][0]["valueReference"]["identifier"]["value"] = dispenser_user_id

        provider = self._contained_resource("PractitionerRole", "provider")
        provider["identifier"][0]["value"] = dispenser_role_id
        provider["practitioner"]["identifier"]["value"] = dispenser_user_id

        organization = self._contained_resource("Organization", "organisation")
        organization["identifier"][0]["value"] = getattr(
            self.context,
            "receiver_ods_code",
            organization["identifier"][0]["value"],
        )

        self.claim_payload["patient"]["identifier"]["value"] = getattr(
            self.context,
            "nhs_number",
            self.claim_payload["patient"]["identifier"]["value"],
        )

        prescription_extension = self.claim_payload["prescription"]["extension"][0]["extension"]
        prescription_extension[0]["valueIdentifier"]["value"] = getattr(
            self.context,
            "prescription_id",
            prescription_extension[0]["valueIdentifier"]["value"],
        )
        prescription_extension[1]["valueIdentifier"]["value"] = getattr(
            self.context,
            "long_prescription_id",
            prescription_extension[1]["valueIdentifier"]["value"],
        )

        item_detail = self.claim_payload["item"][0]["detail"][0]
        item_detail["extension"][0]["valueIdentifier"]["value"] = str(uuid4())
        item_detail["extension"][1]["valueReference"]["identifier"]["value"] = getattr(
            self.context,
            "prescription_item_id",
            item_detail["extension"][1]["valueReference"]["identifier"]["value"],
        )

        item_sub_detail = item_detail["subDetail"][0]
        item_sub_detail["extension"][0]["valueReference"]["identifier"]["value"] = getattr(
            self.context,
            "prescription_item_id",
            item_sub_detail["extension"][0]["valueReference"]["identifier"]["value"],
        )

        if getattr(self.context, "prescription_type", None) == "eRD":
            repeats_issued = getattr(self.context, "number_of_repeats_issued", ERD_DEFAULT_REPEATS_ISSUED)
            repeats_allowed = getattr(self.context, "number_of_repeats_allowed", ERD_DEFAULT_REPEATS_ALLOWED)
            repeat_info_extension = {
                "url": "https://fhir.nhs.uk/StructureDefinition/Extension-EPS-RepeatInformation",
                "extension": [
                    {"url": "numberOfRepeatsIssued", "valueInteger": repeats_issued},
                    {"url": "numberOfRepeatsAllowed", "valueInteger": repeats_allowed},
                ],
            }
            self.claim_payload["item"][0]["extension"].append(repeat_info_extension)

            repeat_info_location = getattr(self.context, "claim_repeat_info_location", None)
            if isinstance(repeat_info_location, str) and repeat_info_location.lower() == "repeat_in_subdetail":
                item_sub_detail["extension"].append(repeat_info_extension)
            else:
                item_detail["extension"].append(repeat_info_extension)

    def _contained_resource(self, resource_type: str, resource_id: str) -> dict:
        return next(
            resource
            for resource in self.claim_payload["contained"]
            if resource.get("resourceType") == resource_type and resource.get("id") == resource_id
        )
