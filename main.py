import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from sift.assess import assess_fit
from sift.email_fetch import fetch_job_urls
from sift.extract import extract_listing
from sift.scrape import scrape_job_page
from sift.store import init_db, save_assessment, url_exists

PROFILE = Path("resources/profile.md").read_text()
CRITERIA = Path("resources/search-criteria.md").read_text()

LOG_PATH = Path("data/failures.log")
MIN_LISTING_LENGTH = 150  # chars — below this, extraction likely caught a wall or empty page


def _strip_params(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


def _log_failure(url: str, source: str, reason: str) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(f"{datetime.now().isoformat()} | {source} | {reason} | {url}\n")


WALL_PATTERNS = ["checkpoint", "login", "authwall", "signin", "sign-in"]

def _is_wall(url: str) -> bool:
    return any(p in url.lower() for p in WALL_PATTERNS)


def main():
    parser = argparse.ArgumentParser(description="Sift — automated job ad screening")
    parser.add_argument("--days", type=int, default=3, help="Fetch emails from the last N days (default: 3)")
    parser.add_argument("--unread", action="store_true", help="Only process unread emails")
    args = parser.parse_args()

    init_db()

    if args.unread:
        print("Fetching job URLs from unread emails...")
        job_urls = fetch_job_urls(unread_only=True)
    else:
        since = date.today() - timedelta(days=args.days)
        print(f"Fetching job URLs from emails since {since}...")
        job_urls = fetch_job_urls(since=since)
    print(f"Found {len(job_urls)} URL(s) across all sources\n")

    seen_canonical: set[str] = set()
    new_count = 0
    skip_count = 0

    for tracking_url, source in job_urls:
        print(f"[{source}] Scraping {tracking_url[:60]}...")

        try:
            job_text, canonical_url = scrape_job_page(tracking_url)
        except Exception as e:
            print(f"  Scrape failed: {e}")
            _log_failure(tracking_url, source, f"scrape_failed: {e}")
            skip_count += 1
            continue

        canonical_url = _strip_params(canonical_url)

        if _is_wall(canonical_url):
            print(f"  Login wall detected — skipping")
            _log_failure(canonical_url, source, "login_wall")
            skip_count += 1
            continue

        if canonical_url in seen_canonical or url_exists(canonical_url):
            print(f"  Already seen — skipping")
            skip_count += 1
            continue

        seen_canonical.add(canonical_url)

        if len(job_text.strip()) < MIN_LISTING_LENGTH:
            print(f"  Page content too short — skipping")
            _log_failure(canonical_url, source, "page_too_short")
            skip_count += 1
            continue

        print(f"  Extracting...")
        try:
            listing = extract_listing(job_text)
        except Exception as e:
            print(f"  Extraction failed: {e}")
            _log_failure(canonical_url, source, f"extraction_failed: {e}")
            skip_count += 1
            continue

        if not listing.is_job_listing:
            print(f"  Not a job listing — skipping")
            _log_failure(canonical_url, source, "not_a_job_listing")
            skip_count += 1
            continue

        print(f"  Assessing...")
        try:
            result = assess_fit(
                listing=listing,
                profile_text=PROFILE,
                criteria_text=CRITERIA,
                url=canonical_url,
                source=source,
            )
        except Exception as e:
            print(f"  Assessment failed: {e}")
            _log_failure(canonical_url, source, f"assessment_failed: {e}")
            skip_count += 1
            continue

        save_assessment(result)
        print(f"  [{result.suggestion}] {result.domain_fit}/{result.role_fit} — saved")
        new_count += 1

    print(f"\nDone. {new_count} new assessments, {skip_count} skipped.")


if __name__ == "__main__":
    main()
