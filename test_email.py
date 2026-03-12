"""
Test email URL extraction.
Prints URLs found in unseen job alert emails — no scraping or assessment.
"""

from sift.email_fetch import fetch_job_urls

if __name__ == "__main__":
    print("Fetching job URLs from email...\n")
    results = fetch_job_urls()

    if not results:
        print("No unseen emails found.")
    else:
        unique_urls = set(url for url, _ in results)
        print(f"Found {len(results)} URL(s), {len(unique_urls)} unique\n")
        for url, source in results:
            print(f"[{source}] {url[:100]}")
