"""
Playwright End-to-End Test Suite for LME Local Web UI.
Verifies setup wizard navigation, pre-filling, custom prompt editing, API interactions,
and analytics dashboard rendering.
"""
import time
import pytest
from http.server import HTTPServer
import threading
from playwright.sync_api import sync_playwright

from backend.web.handlers import WebHandler

TEST_PORT = 8769


@pytest.fixture(scope="module")
def local_web_server():
    server = HTTPServer(("127.0.0.1", TEST_PORT), WebHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)
    yield f"http://127.0.0.1:{TEST_PORT}"
    server.shutdown()


def test_playwright_setup_wizard_end_to_end(local_web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1. Load setup wizard
        page.goto(f"{local_web_server}/setup")
        assert "LME Setup" in page.title()

        # Wait for page to initialize and fetch config
        page.wait_for_selector("#s2")

        # 2. Check credentials auto-skip / badge detection
        # Since credentials exist in .env, step 1 is done and step 2 is active
        time.sleep(1)
        s2_class = page.get_attribute("#s2", "class") or ""
        assert "active" in s2_class, "Expected wizard to auto-advance to step 2 when credentials exist"

        # 3. Step 2 (Candidate Profile)
        exp_input = page.locator("#exp-years")
        assert exp_input.is_visible()
        exp_input.fill("3")

        # Next to Step 3 (AI)
        page.locator("#s2-next").click()
        page.wait_for_selector("#s3.active")

        # 4. Step 3 (AI Scoring & Custom Prompt)
        prompt_box = page.locator("#custom-prompt")
        assert prompt_box.is_visible()
        prompt_content = prompt_box.input_value()
        assert len(prompt_content) > 10, "Custom prompt should be pre-filled from user_prompt.md"
        assert "Candidate Profile" in prompt_content

        # Adjust score threshold slider
        slider = page.locator("#score-thr")
        slider.fill("55")

        # Next to Step 4 (Automate)
        page.locator("#s3-next").click()
        page.wait_for_selector("#s4.active")

        # 5. Step 4 (Automate)
        # Enable cron toggle via label/check
        page.evaluate("document.getElementById('cron-enable').click()")
        page.wait_for_selector("#cron-time")
        assert page.locator("#cron-time").is_visible()
        page.locator("#s4-next").click()
        page.wait_for_selector("#s5.active")

        # 6. Step 5 (Summary & Save)
        summary_div = page.locator("#summary")
        assert summary_div.is_visible()
        save_btn = page.locator("#btn-save")
        assert save_btn.is_visible()

        browser.close()


def test_playwright_dashboard_end_to_end(local_web_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Load analytics dashboard
        page.goto(f"{local_web_server}/dashboard")
        assert "LME Dashboard" in page.title()

        # Verify key analytics stat cards are present
        page.wait_for_selector(".stats")
        stats = page.locator(".stat")
        assert stats.count() >= 4

        # Verify applied jobs table body is present
        tbody = page.locator("#jobs-table-body")
        assert tbody.is_visible()

        browser.close()
