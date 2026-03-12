# Sift
### Automated job ad screening for the other side of the table

---

## What it does

Sift monitors a designated email folder for job alert messages, extracts job ad URLs,
scrapes the listing content, and uses a local LLM to assess fit against a structured
personal profile. Results are stored and browsable via a Streamlit dashboard.

The human decides. Sift surfaces and structures; it does not apply.

---

## Architecture

### Pipeline (nodes, designed for LangGraph migration)
```
fetch_emails()
    → extract_urls()
        → scrape_job_page(url)
            → assess_fit(job_text, profile)
                → store_result(assessment)
```

Each step is a clean, stateless function from day one.
LangGraph wiring is a later refactor, not a rewrite.

### Components

| Component         | Technology                        |
|------------------|-----------------------------------|
| Email monitoring  | imapclient (IMAP, generic)        |
| Web scraping      | Playwright (handles JS rendering, authenticated sessions) |
| LLM assessment    | Ollama (local); structured output |
| Persistence       | SQLite                            |
| Dashboard         | Streamlit                         |

---

## Input sources

Any job board that sends email alerts with links. Currently:
- LinkedIn
- Stepstone
- Goodjobs.eu
- Climatebase
- 80,000 Hours

New sources require no code changes — just subscribe to their alerts.

---

## Profile documents

Two markdown files the LLM reasons against:

- `profile.md` — who I am (background, skills, experience)
- `search-criteria.md` — what I'm looking for (roles, domains, filters)

---

## Assessment output (per job)

Structured, not a single score. Fields:

| Dimension          | Values          | Notes                                      |
|-------------------|-----------------|--------------------------------------------|
| domain_fit        | high/medium/low | Matches target domains?                    |
| role_fit          | high/medium/low | Data-centric, human component?             |
| gap_risk          | high/medium/low | Industry experience requirements vs. profile |
| language          | DE/EN           | Job ad language                            |
| reasoning         | text (2-3 sent) | Why these scores                           |
| suggestion        | apply/consider/skip | Explicit: this is a suggestion only   |
| source            | string          | Which job board                            |
| url               | string          |                                            |
| scraped_at        | datetime        |                                            |

---

## Dashboard (Streamlit)

- Filter by dimension scores, suggestion, domain, source
- Sort by date or fit
- Click through to original listing
- Mark as reviewed / archived

---

## Roadmap

### Phase 1 — Core pipeline
- IMAP monitoring, URL extraction
- Playwright scraping (LinkedIn + Stepstone first)
- Ollama assessment with structured output
- SQLite storage
- Basic Streamlit table view

### Phase 2 — LangGraph migration
- Refactor pipeline functions into LangGraph nodes
- Add conditional edges (e.g. skip assessment if already seen URL)
- Retry logic for failed scrapes

### Phase 3 — Profile interview
- Conversational LLM flow to generate/update search-criteria.md
- Structured interview, written output

---

## Portfolio angle

Built to solve a real personal problem during an active job search.
Demonstrates: agentic pipeline design, web scraping, structured LLM output,
local model deployment, SQLite persistence, Streamlit dashboarding.
Honest framing: the tool automates intake, not decisions.