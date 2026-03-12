from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def scrape_job_page(url: str) -> tuple[str, str]:
    """Fetch a job page. Returns (text, resolved_url) after following redirects."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")

        # Accept cookie consent if present
        try:
            page.get_by_role("button", name="Alles akzeptieren").click(timeout=3000)
            page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            pass  # No cookie banner, carry on

        return page.inner_text("body"), page.url
