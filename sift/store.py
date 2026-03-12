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
        for col in [
            "employer TEXT",
            "job_title TEXT",
            "listing_text TEXT",
            "hidden INTEGER DEFAULT 0",
            "stars INTEGER",
            "summary TEXT DEFAULT '[]'",
            "job_summary TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE assessments ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass

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
                 job_summary, domain_fit, role_fit, gap_risk, reasoning, summary, suggestion,
                 status, hidden, stars)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                a.role_fit,
                a.gap_risk,
                a.reasoning,
                json.dumps(a.summary),
                a.suggestion,
                a.status,
                int(a.hidden),
                a.stars,
            ),
        )


def update_tags(url: str, status: str, hidden: bool, stars: int | None) -> None:
    """Update user-managed fields for an assessment."""
    with _connect() as conn:
        conn.execute(
            "UPDATE assessments SET status = ?, hidden = ?, stars = ? WHERE url = ?",
            (status, int(hidden), stars, url),
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
        d["summary"] = json.loads(d.get("summary") or "[]")
        d["status"] = d.get("status") or "New"
        d["hidden"] = bool(d.get("hidden", 0))
        d["stars"] = d.get("stars")  # None = not yet rated
        results.append(Assessment(**d))
    return results
