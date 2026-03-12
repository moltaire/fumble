import os
from datetime import datetime, timezone
from typing import Literal

import ollama
from dotenv import load_dotenv
from pydantic import BaseModel

from sift.extract import JobListing

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

SYSTEM_PROMPT = """You are a precise job screening assistant.
Assess how well a job listing matches a candidate's profile and search criteria.
Be concise and direct."""

USER_PROMPT = """## Candidate Profile
{profile_text}

## Search Criteria
{criteria_text}

## Job Listing
{listing_text}

---

Assess this job listing against the profile and criteria above.

**First, summarise the job in one sentence** (job_summary): what the role is, at what kind of organisation, and the main focus. Plain text, no jargon.

**Then assess fit on three dimensions:**
- domain_fit (high/medium/low): Match between job domain and the candidate's target domains from Search Criteria. high = primary target domain. medium = adjacent or acceptable. low = unrelated.
- role_fit (high/medium/low): Match between role type and the candidate's target roles from Search Criteria. high = strong match on role type and responsibilities. medium = partial match. low = does not match target role types.
- gap_risk (high/medium/low): Risk of being screened out due to profile gaps. high = role explicitly requires experience the candidate clearly lacks per the profile. medium = some requirements are a stretch. low = profile is a plausible fit.

**Then give:**
- suggestion: apply / consider / skip
- reasoning: 1-2 sentence plain-text prose summary. State the key facts directly. No bullet points here.
- summary: list of 2-3 short bullet strings. Each is a single plain-text phrase, no markdown. Example: ["Core target domain, strong fit", "Requires 3+ yrs industry exp — real gap", "Role type matches well"]
"""


class FitResult(BaseModel):
    """What the LLM produces — purely analytical fields."""

    job_summary: str = ""
    domain_fit: Literal["high", "medium", "low"]
    role_fit: Literal["high", "medium", "low"]
    gap_risk: Literal["high", "medium", "low"]
    reasoning: str
    summary: list[str] = []
    suggestion: Literal["apply", "consider", "skip"]


class Assessment(JobListing, FitResult):
    """Full record — extraction + fit analysis + pipeline metadata."""

    is_job_listing: bool = True  # always true by the time we reach assessment
    url: str
    source: str
    scraped_at: datetime
    status: str = "New"
    hidden: bool = False
    stars: int | None = None


def assess_fit(
    listing: JobListing,
    profile_text: str,
    criteria_text: str,
    url: str = "",
    source: str = "",
) -> Assessment:
    prompt = USER_PROMPT.format(
        profile_text=profile_text,
        criteria_text=criteria_text,
        listing_text=listing.listing_text or "[No listing text extracted]",
    )

    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        format=FitResult.model_json_schema(),
        options={"temperature": 0.2},
    )
    content = response.message.content
    if not content:
        raise ValueError("LLM did not return any content")
    fit = FitResult.model_validate_json(content)

    return Assessment(
        **listing.model_dump(exclude={"is_job_listing"}),
        **fit.model_dump(),
        url=url,
        source=source,
        scraped_at=datetime.now(timezone.utc),
    )
