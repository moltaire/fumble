# Sift — Brainstorming & Future Directions

## Richer detail panel

### Structured fit/gap breakdown
A second LLM call (triggered on demand, not during the pipeline) that produces:
- **Fit points** (green): specific things in the job description that match the profile well
  e.g. "Bayesian modelling explicitly mentioned", "Berlin-based", "Research culture"
- **Gap points** (orange/red): specific things that are a concern
  e.g. "Requires 3+ yrs consulting experience", "Production ML engineering focus", "No research component"
- **Open questions** (grey): things unclear from the job text worth investigating
  e.g. "Unclear if role has autonomy vs. execution only", "Team size unknown"

This would render as a colour-coded list in the detail panel, much more actionable than bullet points.
Could be computed on the fly when a row is selected (lazy evaluation) and stored as JSON in the DB.

### Cover letter starter
A further LLM output: a 2-3 sentence "angle" for a cover letter, given the specific fit points.
Only shown for `apply` or `consider` suggestions.

---

## LangGraph pipeline

The current pipeline is designed for LangGraph migration (clean stateless functions → nodes).

### Near-term, high value
- **Conditional edges**: skip if URL already in DB, retry failed scrapes, route by source
- **Parallel scraping (fanout)**: dispatch all N URLs simultaneously, fan back in to assessor — big speed gain at volume
- **Multiple input adapters**: email is one entry node; paste/file upload would be others feeding the same downstream graph

### Medium-term
- **Duplicate/similarity detection**: embed job text and check cosine similarity against stored jobs before assessing
- **Feedback loop from status**: reads Applied/Rejected patterns and surfaces insights; could inform updates to search-criteria.md

### Longer-term
- **Profile interview agent** (Phase 3): conversational flow to update search-criteria.md based on what's working
- **Alert on strong matches**: push notification when a new `apply`-rated job arrives

---

## Dashboard — UI framework limitations

The core tension: `st.dataframe` supports row selection but not in-cell editing. `st.data_editor` supports editing but not row selection. Selection state is ephemeral — Streamlit rebuilds on every interaction. Currently solved with `st.session_state` to persist selected URL across reruns.

If the dashboard becomes a real daily-use tool, a lightweight web app (FastAPI + HTMX, or small React frontend) would handle stateful tables natively.

---

## Scraping improvements
- Consent-O-Matic extension via Playwright persistent context — handles cookie walls universally
- For LinkedIn: persistent browser context with saved session cookies (log in once manually, reuse)
- Rate limiting / politeness delay between requests to avoid blocks
