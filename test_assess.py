"""
Quick manual test for assess_fit().
Runs against a hardcoded job description — no scraping or email needed.
"""

from pathlib import Path
from fumble.assess import assess_fit
from fumble.store import init_db, load_assessments, save_assessment, url_exists

PROFILE = Path("resources/profile.md").read_text()
CRITERIA = Path("resources/search-criteria.md").read_text()

URL = "https://ecosia.jobs/data-scientist"

JOB_TEXT = """
Data Scientist (m/f/d) — Sustainability & Impact Analytics
Ecosia GmbH · Berlin (hybrid) · Full-time

About us:
Ecosia is the search engine that plants trees. We are a certified B Corp and social business
with a mission to restore ecosystems through technology. Our data team informs product,
growth, and impact strategy.

Your role:
- Design and run experiments (A/B tests) to understand user behaviour and improve retention
- Build models to forecast tree-planting impact and attribute it to product decisions
- Communicate findings clearly to non-technical stakeholders (product, comms, leadership)
- Collaborate with engineers on instrumentation and data pipelines
- Contribute to our open impact reporting

What we're looking for:
- 2+ years working with data in a product or research context
- Strong Python and SQL; experience with experimentation frameworks
- Comfort with statistical methods: regression, causal inference, Bayesian approaches a plus
- Genuine interest in sustainability and mission-driven work
- Clear written and verbal communication in English; German a plus

Nice to have:
- Experience in a startup or scale-up environment
- Familiarity with dbt, Airflow, or similar data tooling

We offer:
- Competitive salary, 30 days vacation, flexible hours
- Berlin office or remote within EU
- Work that directly funds tree planting
"""

if __name__ == "__main__":
    init_db()

    if url_exists(URL):
        print("Already assessed — skipping LLM.")
    else:
        print("Running assess_fit() ...\n")
        result = assess_fit(
            job_text=JOB_TEXT,
            profile_text=PROFILE,
            criteria_text=CRITERIA,
            url=URL,
            source="manual-test",
        )

        print(f"domain_fit:  {result.domain_fit}")
        print(f"role_fit:    {result.role_fit}")
        print(f"gap_risk:    {result.gap_risk}")
        print(f"language:    {result.language}")
        print(f"suggestion:  {result.suggestion}")
        print(f"\nreasoning:\n  {result.reasoning}")

        save_assessment(result)
        print("\nSaved.")

    print("\n--- DB contents ---")
    all_results = load_assessments()
    print(f"{len(all_results)} assessment(s) in DB")
    for r in all_results:
        print(f"  {r.url} → {r.suggestion}")
