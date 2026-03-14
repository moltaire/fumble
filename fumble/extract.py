from typing import Literal

from pydantic import BaseModel

from fumble.llm import EXTRACT_MODEL, call_llm

SYSTEM_PROMPT = """You are a precise text extraction assistant.
Your first job is to determine whether the input actually contains a job listing.
If it does, extract and clean the listing content.
If it does not — e.g. it is a login wall, cookie notice, error page, job search results page, or otherwise lacks a specific job advertisement — set is_job_listing to false and leave all other fields empty."""

USER_PROMPT = """## Raw scraped content
{raw_text}

---

First, decide: does this content contain an actual job listing (a specific job advertisement with description, responsibilities, or requirements)?

Set is_job_listing accordingly, then extract:

- employer: company name (empty string if unclear)
- job_title: exact job title as written (empty string if unclear)
- language: DE or EN based on the job listing language
- listing_text: the cleaned job listing in markdown. Include job description, responsibilities, requirements, and any about-the-company section. Exclude navigation, cookie notices, footer, sidebar, links to other jobs, and other boilerplate. Preserve structure and original wording. Empty string if is_job_listing is false.
"""


class JobListing(BaseModel):
    is_job_listing: bool = False
    employer: str = ""
    job_title: str = ""
    language: Literal["DE", "EN"] = "EN"
    listing_text: str = ""


def extract_listing(raw_text: str) -> JobListing:
    prompt = USER_PROMPT.format(raw_text=raw_text)
    content = call_llm(SYSTEM_PROMPT, prompt, JobListing.model_json_schema(), model=EXTRACT_MODEL)
    return JobListing.model_validate_json(content)
