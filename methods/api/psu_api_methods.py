import json
import logging
from enum import Enum

from messages.psu.prescription_status_update import StatusUpdate
from methods.api.common_api_methods import get, post, get_headers

logger = logging.getLogger(__name__)


class UpdateCoding(Enum):
    WITH_PHARMACY = "With Pharmacy"
    READY_TO_COLLECT = "Ready to Collect"
    READY_TO_COLLECT_PARTIAL = "Ready to Collect - partial"
    COLLECTED = "Collected"


CODING_TO_STATUS_MAP = {
    UpdateCoding.WITH_PHARMACY.value: "in-progress",
    UpdateCoding.READY_TO_COLLECT.value: "in-progress",
    UpdateCoding.READY_TO_COLLECT_PARTIAL.value: "in-progress",
    UpdateCoding.COLLECTED.value: "completed",
}


POST_DATED_ALLOWED_CODINGS = {
    UpdateCoding.READY_TO_COLLECT.value,
    UpdateCoding.READY_TO_COLLECT_PARTIAL.value,
}


def send_status_update(context):
    url = f"{context.psu_base_url.rstrip('/')}/"

    original_post_dated_timestamp = getattr(context, "post_dated_timestamp", None)
    is_post_dated_allowed = getattr(context, "item_status", None) in POST_DATED_ALLOWED_CODINGS

    if original_post_dated_timestamp and not is_post_dated_allowed:
        logger.debug(
            "Ignoring post-dated timestamp for non-eligible coding '%s'",
            getattr(context, "item_status", None),
        )
        delattr(context, "post_dated_timestamp")

    try:
        headers = get_headers(context, "oauth2")
        context.send_update_body = StatusUpdate(context).body
        context.response = post(data=context.send_update_body, url=url, context=context, headers=headers)
    finally:
        if original_post_dated_timestamp and not hasattr(context, "post_dated_timestamp"):
            context.post_dated_timestamp = original_post_dated_timestamp


def check_status_updates(context, prescription_id=None, nhs_number=None, ods_code=None):
    url = f"{context.psu_base_url.rstrip('/')}/checkprescriptionstatusupdates"
    params = {}
    if prescription_id:
        params["prescriptionid"] = prescription_id
    if nhs_number:
        params["nhsnumber"] = nhs_number
    if ods_code:
        params["odscode"] = ods_code

    headers = get_headers(context, "oauth2")
    context.response = get(context=context, url=url, params=params, headers=headers)
    return context.response


def get_status_updates(context):
    body = {
        "schemaVersion": 1,
        "prescriptions": [
            {
                "prescriptionID": context.prescription_id,
                "odsCode": context.receiver_ods_code,
            }
        ],
    }

    headers = get_headers(context, "oauth2")
    context.response = post(data=json.dumps(body), url=context.gsul_base_url, context=context, headers=headers)
    logger.debug("GSUL response: %s", context.response.text)
    return context.response
