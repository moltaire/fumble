#!/usr/bin/env python3
"""Compare extraction pipeline stages for a given URL.

Columns: Raw HTML · Trafilatura XML · Trafilatura Markdown · LLM output

Usage:
    uv run python scripts/compare_extraction.py            # uses test-ads.md
    uv run python scripts/compare_extraction.py <url> ...
"""
import html as html_lib
import sys
import tempfile
import webbrowser
from pathlib import Path

import trafilatura

sys.path.insert(0, str(Path(__file__).parent.parent))

from fumble.extract import extract_listing
from fumble.scrape import (
    BROWSER_PROFILE,
    _extract_jsonld_job,
    _extract_next_data,
    _is_blocked,
    _strip_html,
)

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Extraction pipeline comparison</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #1a1a1a; color: #eee; }}
  h1 {{ font-size: 0.9rem; padding: 0.75rem 1rem; background: #111; margin: 0; color: #aaa; }}
  .job {{ margin: 1.5rem; }}
  .job-header {{ background: #2a2a2a; border: 1px solid #444; border-bottom: none;
                 padding: 0.6rem 1rem; border-radius: 6px 6px 0 0; }}
  .job-header strong {{ font-size: 1rem; }}
  .job-header a {{ color: #7af; font-size: 0.8rem; margin-left: 1rem; }}
  .cols {{ display: grid; grid-template-columns: repeat(4, 1fr);
           border: 1px solid #444; border-radius: 0 0 6px 6px; overflow: hidden; }}
  .col {{ padding: 1rem; overflow-wrap: break-word; border-right: 1px solid #333; }}
  .col:last-child {{ border-right: none; }}
  .col-head {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.07em;
               color: #888; margin: 0 0 0.4rem; display: flex; justify-content: space-between; }}
  .col-head span {{ color: #555; }}
  pre {{ white-space: pre-wrap; font-size: 0.78rem; line-height: 1.5; margin: 0;
         font-family: 'Menlo', 'Consolas', monospace; }}
  .col:nth-child(1) {{ background: #1e1a2a; }}
  .col:nth-child(2) {{ background: #1a2020; }}
  .col:nth-child(3) {{ background: #1a1e28; }}
  .col:nth-child(4) {{ background: #201e1a; }}
</style>
</head>
<body>
<h1>Extraction pipeline — {n} URL(s)</h1>
{jobs}
</body>
</html>"""

JOB_TEMPLATE = """\
<div class="job">
  <div class="job-header">
    <strong>{title} @ {employer}</strong>
    <a href="{url}" target="_blank">{url}</a>
  </div>
  <div class="cols">
    <div class="col">
      <div class="col-head">Raw HTML <span>{raw_html_len:,} chars</span></div>
      <pre>{raw_html}</pre>
    </div>
    <div class="col">
      <div class="col-head">Trafilatura XML <span>{traf_xml_len:,} chars</span></div>
      <pre>{traf_xml}</pre>
    </div>
    <div class="col">
      <div class="col-head">Trafilatura Markdown <span>{traf_md_len:,} chars</span></div>
      <pre>{traf_md}</pre>
    </div>
    <div class="col">
      <div class="col-head">LLM output <span>{llm_len:,} chars</span></div>
      <pre>{llm}</pre>
    </div>
  </div>
</div>"""

RAW_HTML_CHARS = 8_000  # enough to see structure without being overwhelming


def _scrape_raw(url: str) -> tuple[str, str]:
    """Return (raw_html, resolved_url) without any processing."""
    if "linkedin.com" in url:
        from playwright.sync_api import sync_playwright
        BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(BROWSER_PROFILE), headless=True, channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = ctx.new_page()
            page.goto(url, wait_until="load")
            html = page.content()
            resolved = page.url
            ctx.close()
        return html, resolved
    else:
        from curl_cffi import requests as curl_requests
        r = curl_requests.get(url, impersonate="firefox", allow_redirects=True)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        if _is_blocked(r.text):
            raise RuntimeError("Cloudflare block detected")
        return r.text, str(r.url)


def _pick_extractor(html: str, url: str) -> tuple[str, str]:
    """Return (label, text) for the non-trafilatura extractors, or ('trafilatura', '') if none match."""
    if t := _extract_jsonld_job(html):
        return "JSON-LD", t
    if t := _extract_next_data(html):
        return "__NEXT_DATA__", t
    return "trafilatura", ""


def e(s: str) -> str:
    return html_lib.escape(s)


def process(url: str) -> str:
    print(f"\n[{url}]")
    print("  scraping raw HTML...")
    raw_html, resolved_url = _scrape_raw(url)

    print("  running trafilatura XML...")
    traf_xml = trafilatura.extract(
        raw_html, include_tables=False, favor_recall=True,
        include_formatting=True, output_format='xml',
    ) or "(trafilatura returned None)"

    print("  running trafilatura markdown...")
    traf_md = trafilatura.extract(
        raw_html, include_tables=False, favor_recall=True,
        include_formatting=True, output_format='markdown',
    ) or "(trafilatura returned None)"

    print("  running LLM extraction...")
    # Use same priority chain as scrape.py but feed raw_html
    label, pre_text = _pick_extractor(raw_html, resolved_url)
    llm_input = pre_text or traf_md or _strip_html(raw_html)
    result = extract_listing(llm_input)
    print(f"  done — raw={len(raw_html):,}  traf_md={len(traf_md):,}  llm={len(result.listing_text):,} chars")

    return JOB_TEMPLATE.format(
        url=e(resolved_url),
        title=e(result.job_title or "(unknown)"),
        employer=e(result.employer or "(unknown)"),
        raw_html_len=len(raw_html),
        raw_html=e(raw_html[:RAW_HTML_CHARS]) + ("\n…" if len(raw_html) > RAW_HTML_CHARS else ""),
        traf_xml_len=len(traf_xml),
        traf_xml=e(traf_xml),
        traf_md_len=len(traf_md),
        traf_md=e(traf_md),
        llm_len=len(result.listing_text),
        llm=e(result.listing_text),
    )


def _load_test_ads(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text().splitlines() if l.strip().startswith("http")]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        default = Path(__file__).parent.parent / "test-ads.md"
        if default.exists():
            urls = _load_test_ads(default)
            print(f"Loaded {len(urls)} URLs from {default}")
        else:
            print("Usage: uv run python scripts/compare_extraction.py <url> [<url> ...]")
            sys.exit(1)
    else:
        urls = sys.argv[1:]

    jobs_html = "".join(process(url) for url in urls)
    page = HTML_TEMPLATE.format(n=len(urls), jobs=jobs_html)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(page)
        path = f.name

    print(f"\nOpening {path}")
    webbrowser.open(f"file://{path}")
