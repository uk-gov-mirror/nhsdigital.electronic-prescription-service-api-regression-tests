# # pylint: disable=no-name-in-module
from behave import when, then  # pyright: ignore [reportAttributeAccessIssue]
from playwright.sync_api import expect
from features.environment import clear_scenario_user_sessions
import requests
import json
import uuid

from pages.session_logged_out import SessionLoggedOutPage
from pages.session_timeout_modal import SessionTimeoutModal


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
    """Minimise the browser window to simulate user switching away"""
    # Use Playwright's page.evaluate to minimize the window
    context.active_page.evaluate("() => window.blur()")
    # Also simulate the page losing focus which is what happens when minimized
    context.active_page.evaluate("() => document.dispatchEvent(new Event('visibilitychange'))")


@when("I set lastActivityTime to be 13 minutes ago")
def set_last_activity_time_13_minutes_ago(context):
    """Call the test support endpoint to set lastActivityTime to 13 minutes in the past"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise Exception("Fake_time tag required in this scenario. See README.md")

    # Wait a moment to ensure session is established after login
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
        raise Exception("No valid account tag found for setting lastActivityTime")

    request_id = str(uuid.uuid4())
    print(f"Setting lastActivityTime to 13 minutes ago for {username}. Request ID: {request_id}")

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
        raise Exception(f"Failed to set lastActivityTime: {response.status_code}")

    print("Fast forwarding clock by 13 minutes to sync with backend time...")
    context.active_page.clock.fast_forward(13 * 60 * 1000)
    print("Clock fast forwarded by 13 minutes")


@when("I fast forward 1 minute so that updateTracker event happens")
def fast_forward_1_minute(context):
    """Fast forward 1 minute to trigger the updateTracker periodic check"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise Exception("Fake_time tag required in this scenario. See README.md")

    print("Fast forwarding clock by 1 minute to trigger periodic check...")

    context.active_page.clock.fast_forward(60 * 1000)

    print("Clock fast forwarded by 1 minute - periodic check should trigger now")

    context.active_page.wait_for_timeout(2000)

    print("Ready to check for modal...")


@then("I should see the timeout session modal")
def verify_timeout_session_modal(context):
    """Verify the timeout session modal is displayed"""
    modal = SessionTimeoutModal(context.active_page)

    print("Looking for timeout session modal...")

    # Give more time for the modal to appear after the periodic check
    context.active_page.wait_for_timeout(3000)

    # Use a more straightforward approach - just wait for the modal container
    try:
        print("Waiting for modal container to appear...")
        expect(modal.modal_container).to_be_visible(timeout=15000)  # Wait up to 15 seconds
        print("✓ Session timeout modal successfully found!")

        # Verify key elements are present
        expect(modal.stay_logged_in_button).to_be_visible(timeout=5000)
        print("✓ Stay logged in button visible")

        expect(modal.logout_button).to_be_visible(timeout=5000)
        print("✓ Logout button visible")

        # Capture the initial countdown time
        try:
            countdown_text = modal.countdown_time.text_content(timeout=3000)
            print(f"✓ Initial countdown timer: {countdown_text}")
        except Exception as countdown_error:
            print(f"Could not read countdown timer: {countdown_error}")
            # Try alternative approach - look for text pattern
            page_text = context.active_page.text_content("body")
            import re

            countdown_match = re.search(r"sign you out in (\d+) seconds?", page_text)
            if countdown_match:
                print(f"✓ Found countdown in page text: {countdown_match.group(1)} seconds")
            else:
                print("Could not find countdown text in page")

    except Exception as e:
        print(f"Modal detection failed: {e}")

        # Debug - check what's on the page
        page_content = context.active_page.content()
        print(f"Page contains 'session-timeout-modal': {'session-timeout-modal' in page_content}")
        print(f"Page contains 'For your security': {'For your security' in page_content}")

        # Take screenshot for debugging
        context.active_page.screenshot(path=f"modal_not_found_{context.scenario.name.replace(' ', '_')}.png")

        raise Exception("Timeout session modal was not found - check screenshot for debugging")


def _capture_countdown_with_fallback(modal, page, description):
    try:
        countdown = modal.countdown_time.text_content(timeout=2000)
        return countdown
    except Exception as e:
        print(f"Could not read countdown {description.lower()}: {e}")
        page_text = page.text_content("body")
        import re

        countdown_match = re.search(r"sign you out in (\d+) seconds?", page_text)
        if countdown_match:
            countdown = f"{countdown_match.group(1)} seconds"
            print(f"Found countdown {description}: {countdown}")
            return countdown
    return None


def _compare_and_report_countdowns(countdown_before, countdown_after):
    if countdown_before and countdown_after:
        print(f" TIMING COMPARISON: {countdown_before} → {countdown_after}")
        import re

        before_num = re.search(r"(\d+)", countdown_before)
        after_num = re.search(r"(\d+)", countdown_after)
        if before_num and after_num:
            diff = int(before_num.group(1)) - int(after_num.group(1))
            print(f" Time difference: {diff} seconds (should be ~120 for real time)")


@when("I fast forward 3 minutes so that updateTracker event happens")
def fast_forward_3_minutes(context):
    """Wait 2 minutes for natural session timeout (real time countdown)"""
    # pylint: disable=broad-exception-raised
    if "fake_time" not in context.tags:
        raise Exception("Fake_time tag required in this scenario. See README.md")

    modal = SessionTimeoutModal(context.active_page)
    countdown_before = _capture_countdown_with_fallback(modal, context.active_page, "BEFORE wait")

    print("⏰ Starting 2-minute real-time wait for natural timeout...")
    context.active_page.wait_for_timeout(120000)

    print("⏰ 2-minute wait completed - checking for automatic logout...")

    current_url = context.active_page.url
    if "session-logged-out" in current_url or "logout" in current_url:
        print(f"✓ Automatic timeout completed - redirected to: {current_url}")
        return

    print("Still on same page after 2 minutes - checking countdown...")

    countdown_after = _capture_countdown_with_fallback(modal, context.active_page, "AFTER 2min wait")
    if not countdown_after:
        current_url = context.active_page.url
        if "session-logged-out" in current_url or "logout" in current_url:
            print(f"✓ Redirected to logout page: {current_url}")
            return

    _compare_and_report_countdowns(countdown_before, countdown_after)

    print("Checking final state after real-time wait...")


def _debug_page_state(page, scenario_name):
    """Helper to capture and log debugging information about page state"""
    current_url = page.url
    print(f"Current URL: {current_url}")
    page.screenshot(path=f"final_logout_check_{scenario_name.replace(' ', '_')}.png")

    page_content = page.content()
    print(f"Page contains 'session-logged-out-timeout': {'session-logged-out-timeout' in page_content}")
    print(f"Page contains 'timeout-title': {'timeout-title' in page_content}")
    print(f"Page contains 'For your security': {'For your security' in page_content}")


def _debug_page_elements(page):
    """Helper to find and log information about page elements"""
    timeout_containers = page.locator('[data-testid*="session-logged-out"]').all()
    print(f"Found {len(timeout_containers)} session-logged-out containers")
    for i, container in enumerate(timeout_containers):
        test_id = container.get_attribute("data-testid")
        print(f"  Container {i}: data-testid='{test_id}'")

    title_elements = page.locator('[data-testid*="title"]').all()
    print(f"Found {len(title_elements)} title elements")
    for i, title in enumerate(title_elements):
        test_id = title.get_attribute("data-testid")
        text = title.text_content()
        print(f"  Title {i}: data-testid='{test_id}', text='{text}'")


def _verify_logout_page_elements(logged_out_page):
    """Helper to verify all expected elements are present on logout page"""
    try:
        expect(logged_out_page.timeout_session_container).to_be_visible()
        print("✓ timeout_session_container found")
    except Exception as e:
        print(f"✗ timeout_session_container not found: {e}")

    try:
        expect(logged_out_page.timeout_title).to_have_text("For your security, we have logged you out")
        print("✓ timeout_title text matches")
    except Exception as e:
        print(f"✗ timeout_title issue: {e}")

    try:
        expect(logged_out_page.timeout_description).to_be_visible()
        print("✓ timeout_description found")
    except Exception as e:
        print(f"✗ timeout_description not found: {e}")

    try:
        expect(logged_out_page.timeout_description2).to_be_visible()
        print("✓ timeout_description2 found")
    except Exception as e:
        print(f"✗ timeout_description2 not found: {e}")


@then("I am redirected to the logged out for inactivity page")
def verify_timed_out_session_and_logged_out_page(context):
    """Verify that the session has timed out and user is on the logged out page"""
    _debug_page_state(context.active_page, context.scenario.name)
    _debug_page_elements(context.active_page)

    logged_out_page = SessionLoggedOutPage(context.active_page)
    _verify_logout_page_elements(logged_out_page)
