import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import boto3

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


@dataclass
class LambdaInvocationResponse:
    status_code: int
    text: str

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")

    def json(self) -> Any:
        return json.loads(self.text)


def _get_psu_lambda_client(context):
    credentials = getattr(context, "psu_aws_credentials", None)
    if credentials is None:
        raise ValueError("PSU AWS credentials are not available for direct get-status-updates invocation")

    return boto3.client(
        "lambda",
        region_name="eu-west-2",
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials["aws_session_token"],
    )


def _get_psu_cloudformation_client(context):
    credentials = getattr(context, "psu_aws_credentials", None)
    if credentials is None:
        raise ValueError("PSU AWS credentials are not available for direct get-status-updates invocation")

    return boto3.client(
        "cloudformation",
        region_name="eu-west-2",
        aws_access_key_id=credentials["aws_access_key_id"],
        aws_secret_access_key=credentials["aws_secret_access_key"],
        aws_session_token=credentials["aws_session_token"],
    )


def _get_get_status_updates_function_arn(context) -> str:
    cached_function_arn = getattr(context, "psu_get_status_updates_function_arn", "")
    if cached_function_arn:
        return cached_function_arn

    export_name = getattr(context, "psuGetStatusUpdatesFunctionArnExportName", "")
    stack_name = getattr(context, "psuCloudFormationStackName", "")
    if not export_name and not stack_name:
        raise ValueError("PSU get-status-updates export name or CloudFormation stack name must be configured")

    client = _get_psu_cloudformation_client(context)

    if stack_name:
        response = client.describe_stacks(StackName=stack_name)
        for stack in response.get("Stacks", []):
            for output in stack.get("Outputs", []):
                output_value = output.get("OutputValue", "")
                if not output_value:
                    continue

                if export_name and output.get("ExportName") == export_name:
                    context.psu_get_status_updates_function_arn = output_value
                    return output_value

    if export_name:
        paginator = client.get_paginator("list_exports")
        for page in paginator.paginate():
            for export in page.get("Exports", []):
                if export.get("Name") == export_name:
                    function_arn = export.get("Value", "")
                    if function_arn:
                        context.psu_get_status_updates_function_arn = function_arn
                        return function_arn

    if export_name:
        raise ValueError(f"Unable to resolve PSU get-status-updates function ARN from export '{export_name}'")

    raise ValueError(f"Unable to resolve PSU get-status-updates function ARN from stack '{stack_name}'")
def _normalise_lambda_payload(lambda_payload: dict[str, Any]) -> LambdaInvocationResponse:
    status_code = int(lambda_payload.get("statusCode", 200))
    body = lambda_payload.get("body", lambda_payload)

    if isinstance(body, str):
        response_text = body
    else:
        response_text = json.dumps(body)

    return LambdaInvocationResponse(status_code=status_code, text=response_text)


def _invoke_get_status_updates_direct(context, body: dict[str, Any]) -> LambdaInvocationResponse:
    client = _get_psu_lambda_client(context)
    function_arn = _get_get_status_updates_function_arn(context)
    response = client.invoke(
        FunctionName=function_arn,
        InvocationType="RequestResponse",
        Payload=json.dumps(body),
    )
    payload = json.loads(response["Payload"].read().decode("utf-8"))

    if response.get("FunctionError"):
        raise ValueError(f"Direct PSU get-status-updates invocation failed: {payload}")

    return _normalise_lambda_payload(payload)


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

    context.response = _invoke_get_status_updates_direct(context, body)
    logger.debug("GSUL direct invoke response: %s", context.response.text)
    return context.response
