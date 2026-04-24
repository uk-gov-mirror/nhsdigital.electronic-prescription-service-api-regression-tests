# pylint: disable=no-name-in-module
from behave import when, then  # pyright: ignore [reportAttributeAccessIssue]
from playwright.sync_api import expect
from features.environment import clear_scenario_user_sessions
import requests
import json
import uuid

from pages.session_logged_out import SessionLoggedOutPage
from pages.session_timeout_modal import SessionTimeoutModal

FAKE_TIME_TAG_ERROR = "Fake_time tag required in this scenario"


@when("the session expires because of automatic timeout")
def clear_active_session(context):
    # Call clear active session lambda for user
    clear_scenario_user_sessions(context, context.scenario.tags)


@then("I should see the timeout session logged out page")
def verify_timeout_logged_out_page(context):
    """Verify the timeout session logged out page is displayed"""
    logged_out_page = SessionLoggedOutPage(context.active_page)
    expect(logged_out_page.timeout_session_container).to_be_visible()
    expect(logged_out_page.timeout_title).to_have_text("For your security, we have logged you out")
    expect(logged_out_page.timeout_description).to_be_visible()
    expect(logged_out_page.timeout_description2).to_be_visible()


@when("I minimise the browser window")
def minimise_browser_window(context):
    context.active_page.evaluate("() => window.blur()")
    context.active_page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")


@when("I set lastActivityTime to be 13 minutes ago")
def set_last_activity_time_13_minutes_ago(context):
    """Call the test support endpoint to set lastActivityTime to 13 minutes in the past"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise ValueError(FAKE_TIME_TAG_ERROR)

    context.active_page.wait_for_timeout(3000)

    # Determine username based on scenario tags
    username = None
    for tag in context.scenario.tags:
        if tag == "single_access":
            username = "Mock_555043300081"
            break
        elif tag == "multiple_access":
            username = "Mock_555043308597"
            break
        elif tag == "multiple_access_pre_selected":
            username = "Mock_555043304334"
            break
        elif tag == "multiple_roles_single_access":
            username = "Mock_555043303739"
            break

    if not username:
        raise ValueError("No valid account tag found for setting lastActivityTime")

    request_id = str(uuid.uuid4())

    payload = json.dumps({"username": username, "request_id": request_id})

    response = requests.post(
        f"{context.cpts_ui_base_url}/api/test-support-fake-timer",
        data=payload,
        headers={
            "Source": f"{context.scenario.name}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )

    if response.status_code != 200:
        print(f"Failed to set lastActivityTime. Response: {response.status_code} - {response.text}")
        response.raise_for_status()

    context.active_page.clock.fast_forward(13 * 60 * 1000)


@when("I fast forward 1 minute so that updateTracker event happens")
def fast_forward_1_minute(context):
    """Fast forward 1 minute to trigger the updateTracker periodic check"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise ValueError(FAKE_TIME_TAG_ERROR)

    context.active_page.clock.fast_forward(60 * 1000)

    context.active_page.wait_for_timeout(2000)


@then("I should see the timeout session modal")
def verify_timeout_session_modal(context):
    """Verify the timeout session modal is displayed"""
    modal = SessionTimeoutModal(context.active_page)
    context.active_page.wait_for_timeout(3000)

    try:
        expect(modal.modal_container).to_be_visible(timeout=15000)
        expect(modal.stay_logged_in_button).to_be_visible(timeout=5000)
        expect(modal.logout_button).to_be_visible(timeout=5000)
    except (TimeoutError, AssertionError) as e:
        print(f"Modal detection failed: {e}")
        page_content = context.active_page.content()
        print(f"Page contains 'session-timeout-modal': {'session-timeout-modal' in page_content}")
        print(f"Page contains 'For your security': {'For your security' in page_content}")
        raise AssertionError("Timeout session modal was not found")


def _capture_countdown_with_fallback(modal, page, description):
    try:
        countdown = modal.countdown_time.text_content(timeout=2000)
        return countdown
    except (TimeoutError, AttributeError) as e:
        print(f"Could not read countdown {description.lower()}: {e}")
        page_text = page.text_content("body")
        import re

        countdown_match = re.search(r"sign you out in (\d+) seconds?", page_text)
        if countdown_match:
            countdown = f"{countdown_match.group(1)} seconds"
            return countdown
    return None


@when("I fast forward 2 minutes so that updateTracker event happens")
def fast_forward_2_minutes(context):
    """Wait 2 minutes for natural session timeout"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise ValueError(FAKE_TIME_TAG_ERROR)

    modal = SessionTimeoutModal(context.active_page)

    context.active_page.wait_for_timeout(120000)

    expected_logout_path = "session-logged-out"
    current_url = context.active_page.url
    if expected_logout_path in current_url:
        return

    countdown_after = _capture_countdown_with_fallback(modal, context.active_page, "AFTER 2min wait")
    if not countdown_after:
        expected_logout_paths = ["session-logged-out", "logout"]
        current_url = context.active_page.url
        if any(path in current_url for path in expected_logout_paths):
            return


@then("I am redirected to the logged out for inactivity page")
def verify_timed_out_session_and_logged_out_page(context):
    """Verify that the session has timed out and user is on the logged out page"""
    logged_out_page = SessionLoggedOutPage(context.active_page)
    expect(logged_out_page.timeout_session_container).to_be_visible()
    expect(logged_out_page.timeout_title).to_have_text("For your security, we have logged you out")
    expect(logged_out_page.timeout_description).to_be_visible()
    expect(logged_out_page.timeout_description2).to_be_visible()
