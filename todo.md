# Sift — TODO

## LinkedIn
- [ ] Auth: persistent browser context, log in once manually, reuse session cookies
- [ ] Test end-to-end with LinkedIn job URLs

## Pipeline
- [ ] Retry failed scrapes before silently skipping
- [ ] Review failures.log after first real run — tune MIN_LISTING_LENGTH and is_job_listing prompt if needed

## Dashboard
- [ ] Richer LLM analysis per job (see brainstorming.md): colour-coded fit/gap breakdown, open questions
- [ ] Consider on-demand second LLM call for structured fit/gap detail (lazy, stored in DB)

## LangGraph migration
- [ ] Refactor pipeline into LangGraph nodes (extract → assess → store)
- [ ] Add parallel fanout for URL scraping
- [ ] Add input adapters: paste / file upload alongside email
