import json
import sqlite3
from datetime import datetime
from pathlib import Path

from sift.assess import Assessment

DB_PATH = Path("data/sift.db")

STATUS_PROGRESSION = ["New", "Researching", "Applied", "Rejected"]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the assessments table and apply any missing migrations."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT UNIQUE,
                source       TEXT,
                scraped_at   TEXT,
                employer     TEXT,
                job_title    TEXT,
                language     TEXT,
                listing_text TEXT,
                domain_fit   TEXT,
                role_fit     TEXT,
                gap_risk     TEXT,
                job_summary  TEXT,
                reasoning    TEXT,
                summary      TEXT DEFAULT '[]',
                suggestion   TEXT,
                status       TEXT DEFAULT 'New',
                hidden       INTEGER DEFAULT 0,
                stars        INTEGER
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_urls (
                url      TEXT PRIMARY KEY,
                seen_at  TEXT NOT NULL
            )
        """
        )

        for col in [
            "employer TEXT",
            "job_title TEXT",
            "listing_text TEXT",
            "hidden INTEGER DEFAULT 0",
            "stars INTEGER",
            "summary TEXT DEFAULT '[]'",
            "job_summary TEXT",
            "domain_fit_reason TEXT",
            "role_fit_reason TEXT",
            "gap_risk_reason TEXT",
            "fit_areas TEXT DEFAULT '[]'",
            "gaps TEXT DEFAULT '[]'",
            "bookmarked INTEGER DEFAULT 0",
            "rating TEXT DEFAULT 'new'",
        ]:
            try:
                conn.execute(f"ALTER TABLE assessments ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass

        # Migrate bookmarked/hidden → rating
        conn.execute(
            "UPDATE assessments SET rating = 'liked' WHERE bookmarked = 1 AND (rating IS NULL OR rating = 'new')"
        )
        conn.execute(
            "UPDATE assessments SET rating = 'disliked' WHERE hidden = 1 AND bookmarked = 0 AND (rating IS NULL OR rating = 'new')"
        )

        # Migrate status from old JSON list format → plain string + hidden flag
        rows = conn.execute(
            "SELECT url, status FROM assessments WHERE status LIKE '[%'"
        ).fetchall()
        for row in rows:
            try:
                tags = json.loads(row["status"])
                new_status = next((t for t in tags if t in STATUS_PROGRESSION), "New")
                new_hidden = 1 if any(t in ("Hidden", "Hide") for t in tags) else 0
            except (json.JSONDecodeError, Exception):
                new_status = "New"
                new_hidden = 0
            conn.execute(
                "UPDATE assessments SET status = ?, hidden = ? WHERE url = ?",
                (new_status, new_hidden, row["url"]),
            )


def save_assessment(a: Assessment) -> None:
    """Insert one assessment. Skips silently if the URL already exists."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO assessments
                (url, source, scraped_at, employer, job_title, language, listing_text,
                 job_summary, domain_fit, domain_fit_reason, role_fit, role_fit_reason,
                 gap_risk, gap_risk_reason, fit_areas, gaps, reasoning, summary,
                 suggestion, status, hidden, stars)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                a.url,
                a.source,
                a.scraped_at.isoformat(),
                a.employer,
                a.job_title,
                a.language,
                a.listing_text,
                a.job_summary,
                a.domain_fit,
                a.domain_fit_reason,
                a.role_fit,
                a.role_fit_reason,
                a.gap_risk,
                a.gap_risk_reason,
                json.dumps(a.fit_areas),
                json.dumps([g.model_dump() for g in a.gaps]),
                a.reasoning,
                json.dumps(a.summary),
                a.suggestion,
                a.status,
                int(a.hidden),
                a.stars,
            ),
        )


def update_assessment(a: Assessment) -> None:
    """Overwrite analytical fields for an existing assessment, preserving user-managed fields."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE assessments SET
                source = ?, scraped_at = ?, employer = ?, job_title = ?, language = ?,
                listing_text = ?, job_summary = ?, domain_fit = ?, domain_fit_reason = ?,
                role_fit = ?, role_fit_reason = ?, gap_risk = ?, gap_risk_reason = ?,
                fit_areas = ?, gaps = ?, reasoning = ?, summary = ?, suggestion = ?
            WHERE url = ?
        """,
            (
                a.source,
                a.scraped_at.isoformat(),
                a.employer,
                a.job_title,
                a.language,
                a.listing_text,
                a.job_summary,
                a.domain_fit,
                a.domain_fit_reason,
                a.role_fit,
                a.role_fit_reason,
                a.gap_risk,
                a.gap_risk_reason,
                json.dumps(a.fit_areas),
                json.dumps([g.model_dump() for g in a.gaps]),
                a.reasoning,
                json.dumps(a.summary),
                a.suggestion,
                a.url,
            ),
        )


def update_rating(url: str, rating: str) -> None:
    """Update the user rating (new | liked | disliked) for an assessment."""
    with _connect() as conn:
        conn.execute(
            "UPDATE assessments SET rating = ? WHERE url = ?",
            (rating, url),
        )


def delete_assessment(url: str) -> None:
    """Permanently remove an assessment from the database."""
    with _connect() as conn:
        conn.execute("DELETE FROM assessments WHERE url = ?", (url,))


def url_exists(url: str) -> bool:
    """Return True if this URL has already been assessed."""
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM assessments WHERE url = ?", (url,)).fetchone()
    return row is not None


def tracking_url_seen(url: str) -> bool:
    """Return True if this tracking URL has already been processed in a previous run."""
    with _connect() as conn:
        row = conn.execute("SELECT 1 FROM seen_urls WHERE url = ?", (url,)).fetchone()
    return row is not None


def mark_url_seen(url: str) -> None:
    """Record a tracking URL as processed so it can be skipped in future runs."""
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_urls (url, seen_at) VALUES (?, ?)",
            (url, datetime.now().isoformat()),
        )


def load_assessments() -> list[Assessment]:
    """Return all stored assessments, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM assessments ORDER BY scraped_at DESC"
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["scraped_at"] = datetime.fromisoformat(d["scraped_at"])
        d["employer"] = d.get("employer") or ""
        d["job_title"] = d.get("job_title") or ""
        d["listing_text"] = d.get("listing_text") or ""
        d["job_summary"] = d.get("job_summary") or ""
        d["domain_fit_reason"] = d.get("domain_fit_reason") or ""
        d["role_fit_reason"] = d.get("role_fit_reason") or ""
        d["gap_risk_reason"] = d.get("gap_risk_reason") or ""
        d["fit_areas"] = json.loads(d.get("fit_areas") or "[]")
        d["gaps"] = json.loads(d.get("gaps") or "[]")
        d["summary"] = json.loads(d.get("summary") or "[]")
        d["status"] = d.get("status") or "New"
        d["rating"] = d.get("rating") or "new"
        d["hidden"] = bool(d.get("hidden", 0))
        d["bookmarked"] = bool(d.get("bookmarked", 0))
        d["stars"] = d.get("stars")  # None = not yet rated
        results.append(Assessment(**d))
    return results
