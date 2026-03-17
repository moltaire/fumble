# Embedding-Based Spam Classifier — Spec

## Goal

Replace (or augment) the keyword-based spam check with an embedding similarity
classifier. The keyword list misses title variations like "intern" or "Werkstudent"
that aren't explicitly listed. An embedding classifier generalises from your existing
labelled corpus without needing exhaustive keyword maintenance.

---

## Current Pipeline Context

The spam check sits **post-extraction, pre-assessment** in `main.py`:

```
scrape → wall/size check → triage → extract (LLM) → [SPAM CHECK] → assess (LLM)
```

`extract` gives us clean `job_title` and `employer` fields, which are the primary
signal. The embedding classifier replaces the keyword match and LLM semantic check at
this same position.

---

## Existing DB: `assessments` table (`data/fumble.db`)

Defined and managed in `fumble/store.py`. Relevant columns:

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `url` | TEXT UNIQUE | Canonical job URL |
| `employer` | TEXT | Extracted by LLM |
| `job_title` | TEXT | Extracted by LLM |
| `listing_text` | TEXT | Full cleaned markdown ad text |
| `rating` | TEXT | User label — see below |
| `assessed_at` | TEXT | ISO timestamp |

### Rating values (the label source)

| `rating` | Meaning |
|---|---|
| `new` | Unreviewed — not used for training |
| `superliked` | Definite yes |
| `liked` | Positive |
| `disliked` | User hid it — wrong fit |
| `spam` | Auto or manually marked spam |

Access via `store.load_assessments()` (excludes spam) and `store.load_spam()`.
For training, query directly:

```sql
SELECT id, job_title, employer, listing_text, rating
FROM assessments
WHERE rating IN ('spam', 'superliked', 'liked', 'disliked')
```

---

## Label Mapping (binary)

| `rating` | Training label |
|---|---|
| `spam` | `spam` |
| `disliked` | `spam` (borderline — included as negative signal) |
| `superliked`, `liked` | `good` |
| `new` | _(inference only, not used for training)_ |

`disliked` is included in the spam class because they are both "don't assess this"
outcomes. If they turn out to cluster separately in embedding space, this can be
revisited as a 3-class setup later.

---

## New Table: `embeddings`

Add to `init_db()` in `fumble/store.py`:

```sql
CREATE TABLE IF NOT EXISTS embeddings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    model         TEXT NOT NULL,   -- e.g. "nomic-embed-text"
    input_type    TEXT NOT NULL,   -- "title" or "listing"
    embedding     BLOB NOT NULL,   -- numpy float32 array, little-endian, row-major
    embedded_at   TEXT NOT NULL    -- ISO timestamp
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_embeddings_unique
    ON embeddings(assessment_id, model, input_type);
```

### Serialisation

```python
import numpy as np

# Store
vec: np.ndarray  # shape (dims,), dtype float32
blob = vec.astype(np.float32).tobytes()

# Load
vec = np.frombuffer(blob, dtype=np.float32)
```

Storage cost: 768 dims × 4 bytes = ~3 KB per row. 200 ads × 2 input types ≈ 1.2 MB
total. Negligible.

---

## Embedding Model

Use Ollama's `/api/embed` endpoint (already a dependency via `ollama>=0.4`).

**Recommended: `nomic-embed-text`**
- 768 dimensions
- Good multilingual quality (handles German job titles well)
- Fast — embedding a short title takes single-digit milliseconds locally
- Standard Ollama pull: `ollama pull nomic-embed-text`

The embedding model is **fixed and frozen** — it is only used as a feature extractor.
There is nothing to train or fine-tune.

---

## Input Features

### Primary: title input

```python
f"{job_title} at {employer}"
# e.g. "Werkstudent Backend at Acme GmbH"
```

Used as the main spam gate. Short, fast to embed, captures most spam signal at the
same position as the current keyword check.

### Secondary: listing input

```python
listing_text  # full cleaned markdown from extraction
```

More signal for subtle cases, but heavier. Embed and store during backfill; use for
offline experiments. Not on the critical path initially.

---

## Classifier

### Centroid-based (start here)

Compute one mean vector per class from all labelled embeddings:

```python
spam_centroid  = mean of all embedding vectors where label == "spam"
good_centroid  = mean of all embedding vectors where label == "good"
```

Classify a new vector by cosine similarity to each centroid — assign the class of the
nearer centroid.

```python
from numpy.linalg import norm

def cosine_sim(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

def classify(vec, spam_centroid, good_centroid) -> str:
    return "spam" if cosine_sim(vec, spam_centroid) > cosine_sim(vec, good_centroid) else "good"
```

**There are no parameters to tune.** Centroids are recomputed from the labelled set on
every run — this takes milliseconds for ~200 vectors.

### kNN (upgrade path)

Find k nearest neighbours in the labelled set by cosine distance, majority vote.
More robust to irregular cluster shapes but needs more labelled data. Revisit once the
corpus grows.

---

## Pipeline Integration

In `main.py`, after extraction, before `assess_fit`:

```python
from fumble.embeddings import embed_text, classify_spam
from fumble import store

# After extraction gives us job_title + employer:
vec = embed_text(f"{listing.job_title} at {listing.employer}", model="nomic-embed-text")
labelled = store.load_labelled_embeddings(model="nomic-embed-text", input_type="title")

if len(labelled) >= 10:  # need minimum corpus before trusting it
    label = classify_spam(vec, labelled)
    if label == "spam":
        # same handling as current keyword/LLM spam path
        ...
```

Keep the keyword check as a fast pre-filter (zero embedding cost for known-obvious
cases). The embedding check runs for anything that passes keywords.

---

## New Module: `fumble/embeddings.py`

```python
def embed_text(text: str, model: str = "nomic-embed-text") -> np.ndarray
    """Call Ollama /api/embed and return a float32 vector."""

def store_embedding(assessment_id: int, model: str, input_type: str, vec: np.ndarray) -> None
    """Upsert an embedding into the embeddings table."""

def load_labelled_embeddings(model: str, input_type: str) -> list[tuple[np.ndarray, str]]
    """Return [(vec, label), ...] for all assessments with a training label."""

def classify_spam(vec: np.ndarray, labelled: list[tuple[np.ndarray, str]]) -> str
    """Centroid-based binary classify. Returns 'spam' or 'good'."""

def backfill(model: str = "nomic-embed-text") -> None
    """Embed all assessments that don't yet have an embedding stored."""
```

---

## Experiment Sequence

1. **Backfill** — run `backfill()` on the existing 181 assessments to populate the
   `embeddings` table. Both `title` and `listing` input types.
2. **Offline eval** — leave-one-out cross-validation on the labelled subset. Check
   precision/recall for the `spam` class specifically (false negatives = missed spam,
   false positives = good jobs blocked).
3. **Compare inputs** — does `title` alone match `listing` quality? If yes, keep title
   as the only inference-time input (cheaper).
4. **Wire in** — add to pipeline behind a flag (`--no-embedding-filter`) so you can
   fall back to LLM-only if needed.
5. **Iterate** — every new manual spam/good rating automatically improves the centroid
   next run. No explicit retraining step required.

---

## Experiment Outcome (March 2026)

The classifier was built and evaluated via leave-one-out cross-validation on 186 labelled
assessments (68 spam / 118 good, after correcting label mapping so disliked→good).

**Results:**
- Centroid (title): Precision 69%, Recall 62%
- kNN k=7 (title): Precision 75%, Recall 62%

**Conclusion:** Performance is insufficient for production use. The embedding space has
too much cluster overlap to reliably separate spam from good at this corpus size.
Recall of 62% means ~38% of spam passes through — unacceptable for a pre-filter.

The `embeddings` table remains in the schema for future use as more labelled data
accumulates. The classifier code (`fumble/embeddings.py`) was removed to avoid dead
code in the pipeline.

As an alternative, an LLM-based title spam check (qwen3.5:9b, think=False) was also
evaluated: Precision 100%, Recall 16% at ~1.9s/call. Too low recall to be useful.
The current pipeline retains keyword-on-title + LLM-on-listing (TRIAGE_MODEL) as the
spam check.
