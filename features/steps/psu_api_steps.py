from datetime import UTC, datetime, timedelta
import json
import logging
import time
import uuid

# pylint: disable=no-name-in-module
from behave import given, when, then  # pyright: ignore [reportAttributeAccessIssue]

from methods.api.psu_api_methods import (
    get_status_updates,
    send_status_update,
    check_status_updates,
)
from methods.api.psu_api_methods import CODING_TO_STATUS_MAP, POST_DATED_ALLOWED_CODINGS
from features.environment import AWS_ROLES
from methods.shared import common
from methods.shared.common import get_auth, assert_that
from utils.prescription_id_generator import generate_short_form_id
from utils.random_nhs_number_generator import generate_single

POST_DATED_DELAY = 10  # Time to wait for post-dated updates to mature
logger = logging.getLogger(__name__)


def _parse_last_modified(item):
    """Parse LastModified timestamp from PSU response item."""
    last_modified = item.get("LastModified") or item.get("lastUpdateDateTime")
    if not isinstance(last_modified, str):
        return None

    try:
        return datetime.fromisoformat(last_modified.replace("Z", "+00:00"))
    except ValueError:
        return None


def _select_latest_effective_item(items):
    """Select latest update whose LastModified is not in the future.

    Falls back to latest dated item, then first item if no parseable dates exist.
    """
    now = datetime.now(UTC)
    parsed_items = [(_parse_last_modified(item), item) for item in items]

    effective_items = [(parsed, item) for parsed, item in parsed_items if parsed and parsed <= now]
    if effective_items:
        return max(effective_items, key=lambda parsed_item: parsed_item[0])[1]

    dated_items = [(parsed, item) for parsed, item in parsed_items if parsed]
    if dated_items:
        return max(dated_items, key=lambda parsed_item: parsed_item[0])[1]

    return items[0]


def _extract_get_status_updates_items(response_data, prescription_id):
    """Extract all items for a specific prescription from get-status-updates response."""
    prescriptions = response_data.get("prescriptions", [])
    matching_prescriptions = [
        prescription for prescription in prescriptions if prescription.get("prescriptionID") == prescription_id
    ]

    if not matching_prescriptions:
        return []

    items = []
    for prescription in matching_prescriptions:
        items.extend(prescription.get("items", []))
    date_codes = [
        {
            "LastModified": item.get("LastModified"),
            "lastUpdateDateTime": item.get("lastUpdateDateTime"),
            "Status": item.get("Status"),
        }
        for item in items
    ]
    logger.debug("Prescription %s has %d items %s", prescription_id, len(items), date_codes)
    return items


@given("I am authorised to send prescription updates")
@when("I am authorised to send prescription updates")
def i_am_authorised_to_send_prescription_updates(context):
    env = context.config.userdata["env"].lower()
    if "sandbox" in env:
        return
    context.auth_token = get_auth(env, "PSU")
    role_arn = AWS_ROLES["psu"]["role_id"]
    if isinstance(role_arn, str):
        role_arn = role_arn.strip()
    if not role_arn:
        raise ValueError(
            "Role ARN for 'psu' is not configured or is blank in environment variables"
        )
    context.psu_aws_credentials = common.assume_aws_role(role_arn=role_arn, session_name="regression_tests_psu")


@given("status updates are enabled")
def step_impl(context):
    env = context.config.userdata["env"].lower()
    if "int" == env:
        context.config.status_updates_enabled = True
    else:
        context.config.status_updates_enabled = False


def send_status_update_helper(context, coding, status, post_dated_timestamp=None):
    """Helper function to send a status update with the given coding and status values."""
    if "e2e" not in context.tags or "sandbox" in context.config.userdata["env"].lower():
        context.receiver_ods_code = "FA565"
        context.prescription_id = generate_short_form_id(context.receiver_ods_code)
        context.prescription_item_id = uuid.uuid4()
        context.nhs_number = generate_single()

    if post_dated_timestamp:
        context.post_dated_timestamp = post_dated_timestamp
    elif hasattr(context, "post_dated_timestamp"):
        delattr(context, "post_dated_timestamp")

    if post_dated_timestamp is None and hasattr(context, "post_dated_delay"):
        delattr(context, "post_dated_delay")

    context.terminal_status = status
    context.item_status = coding
    logger.debug(
        "Sending update for prescription ID: %s: coding: %s status: %s", context.prescription_id, coding, status
    )
    try:
        send_status_update(context)
    finally:
        if hasattr(context, "post_dated_timestamp"):
            delattr(context, "post_dated_timestamp")


@when("I send a '{coding}' update with a status of '{status}'")
def i_send_an_update(context, coding, status):
    send_status_update_helper(context, coding, status)


@when("I send a '{coding}' update")
def i_send_an_update_without_status(context, coding):
    if coding not in CODING_TO_STATUS_MAP:
        raise ValueError(f"Unknown coding '{coding}'. Supported codings: {', '.join(CODING_TO_STATUS_MAP.keys())}")
    status = CODING_TO_STATUS_MAP[coding]
    send_status_update_helper(context, coding, status)


@when("I send a '{coding}' post-dated update")
def i_send_a_postdated_update(context, coding):
    """Send a post-dated status update with lastModified timestamp in the future."""
    if coding not in CODING_TO_STATUS_MAP:
        raise ValueError(f"Unknown coding '{coding}'. Supported codings: {', '.join(CODING_TO_STATUS_MAP.keys())}")

    if coding not in POST_DATED_ALLOWED_CODINGS:
        raise ValueError(
            "Post-dated updates are only allowed for these codings: " f"{', '.join(sorted(POST_DATED_ALLOWED_CODINGS))}"
        )

    status = CODING_TO_STATUS_MAP[coding]

    try:
        post_dated_delay = int(context.config.userdata.get("post_dated_delay", POST_DATED_DELAY))
    except (TypeError, ValueError) as err:
        raise ValueError("'post_dated_delay' must be an integer number of seconds") from err

    if post_dated_delay < 0:
        raise ValueError("'post_dated_delay' must be zero or greater")

    context.post_dated_delay = post_dated_delay

    # Calculate future timestamp
    post_dated_timestamp = (datetime.now(UTC) + timedelta(seconds=post_dated_delay)).isoformat()

    logger.debug(
        "Sending post-dated update for %s at: %s",
        getattr(context, "prescription_id", None),
        post_dated_timestamp,
    )
    send_status_update_helper(context, coding, status, post_dated_timestamp=post_dated_timestamp)


@when("I advance the clock to beyond the post-dated time")
def advance_clock_beyond_postdated(context):
    """Poll the API until the post-dated time has passed and status update takes effect."""
    if "sandbox" in context.config.userdata["env"].lower():
        logger.debug("Skipping clock advancement in sandbox environment")
        return

    prescription_id = context.prescription_id
    expected_coding = context.item_status

    # Polling configuration
    timeout = context.post_dated_delay * 1.2  # allow 20% buffer beyond post-dated delay before giving up
    period = max(2, context.post_dated_delay / 10)  # poll at reasonable intervals, at least every 2 seconds
    mustend = time.time() + timeout
    time.sleep(context.post_dated_delay)

    logger.debug("Poll for update that should now have matured (timeout: %ss, interval: %ss)", mustend, period)
    while time.time() < mustend:
        response = check_status_updates(context, prescription_id=prescription_id)

        if response.status_code == 200:
            response_data = json.loads(response.content)
            matching_items = [
                items for items in response_data.get("items", []) if items.get("PrescriptionID") == prescription_id
            ]

            if matching_items:
                item = _select_latest_effective_item(matching_items)
                current_status = item.get("Status")
                logger.debug(
                    "Current effective status: %s (LastModified: %s), Expected: %s",
                    current_status,
                    item.get("LastModified"),
                    expected_coding,
                )

                # Check if the post-dated update has taken effect
                if current_status == expected_coding:
                    logger.debug("Post-dated status update has taken effect: %s", expected_coding)
                    return

        time.sleep(period)
    raise TimeoutError(
        f"Post-dated status update did not take effect within {timeout} seconds. Expected status: {expected_coding}"
    )


@then("The prescription item has a coding of '{expected_coding}' with a status of '{expected_status}'")
def verify_update_recorded(context, expected_coding, expected_status):
    if "sandbox" in context.config.userdata["env"].lower():
        logger.debug("Skipping verification in sandbox environment")
        return

    prescription_id = context.prescription_id

    response = get_status_updates(context)
    assert_that(response.status_code).is_equal_to(200)

    response_data = json.loads(response.content)
    matching_items = _extract_get_status_updates_items(response_data, prescription_id)
    if matching_items:
        item = _select_latest_effective_item(matching_items)

        # get-status-updates response shape
        if "latestStatus" in item:
            assert_that(item.get("latestStatus")).is_equal_to(expected_coding)
            expected_terminal_state = expected_status.strip().lower() == "completed"
            assert_that(item.get("isTerminalState")).is_equal_to(expected_terminal_state)
            return

        assert_that(item.get("TerminalStatus")).is_equal_to(expected_status)
        assert_that(item.get("Status")).is_equal_to(expected_coding)


@then("'{expected_count:d}' updates are returned from get-status-updates endpoint")
def verify_updates_count(context, expected_count):
    if "sandbox" in context.config.userdata["env"].lower():
        logger.debug("Skipping verification in sandbox environment")
        return

    prescription_id = context.prescription_id

    response = get_status_updates(context)
    assert_that(response.status_code).is_equal_to(200)

    response_data = json.loads(response.content)
    matching_items = _extract_get_status_updates_items(response_data, prescription_id)

    assert_that(len(matching_items)).is_equal_to(expected_count)
