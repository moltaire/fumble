from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BROWSER_PROFILE = Path("data/browser_profile")


def scrape_job_page(url: str) -> tuple[str, str]:
    """Fetch a job page using a persistent browser context (preserves login state).
    Returns (text, resolved_url) after following redirects."""
    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE),
            headless=True,
        )
        page = context.new_page()
        page.goto(url, wait_until="load")

        # Accept cookie consent if present
        try:
            page.get_by_role("button", name="Alles akzeptieren").click(timeout=3000)
        except PlaywrightTimeoutError:
            pass  # No cookie banner, carry on

        result = page.inner_text("body"), page.url
        context.close()
        return result


def login_flow(start_url: str = "https://www.linkedin.com/login") -> None:
    """Open a headed browser for manual login, then save the session."""
    BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(BROWSER_PROFILE),
            headless=False,
        )
        page = context.new_page()
        page.goto(start_url, wait_until="load")
        print("Log in, then press Enter here to save the session and close the browser.")
        input()
        context.close()
