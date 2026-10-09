import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    employment_type TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    team TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL DEFAULT '',
    source_query TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, external_id)
);
CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status);
"""


class JobStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def upsert_many(self, jobs: Iterable[Job]) -> tuple[int, int]:
        added = updated = 0
        for job in jobs:
            existing = self.db.execute(
                "SELECT id FROM jobs WHERE source = ? AND external_id = ?",
                (job.source, job.external_id),
            ).fetchone()
            values = (job.source, job.external_id, job.title, job.company, job.location,
                      job.description, job.url, job.employment_type, job.department,
                      job.team, job.published_at, job.source_query)
            if existing:
                self.db.execute("""UPDATE jobs SET title=?, company=?, location=?, description=?,
                    url=?, employment_type=?, department=?, team=?, published_at=?, source_query=?,
                    updated_at=CURRENT_TIMESTAMP WHERE source=? AND external_id=?""",
                    values[2:] + values[:2])
                updated += 1
            else:
                self.db.execute("""INSERT INTO jobs
                    (source, external_id, title, company, location, description, url,
                     employment_type, department, team, published_at, source_query)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
                added += 1
        self.db.commit()
        return added, updated

    def list(self, status: str | None = None, query: str | None = None, limit: int = 50):
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if query:
            clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
            term = f"%{query}%"
            params.extend([term, term, term])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.db.execute(
            f"SELECT * FROM jobs {where} ORDER BY id DESC LIMIT ?", (*params, limit)
        ).fetchall()

    def get(self, job_id: int):
        return self.db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def set_status(self, job_id: int, status: str) -> bool:
        cursor = self.db.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, job_id),
        )
        self.db.commit()
        return cursor.rowcount > 0

    def delete(self, job_id: int) -> bool:
        cursor = self.db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        self.db.commit()
        return cursor.rowcount > 0

    def reset(self) -> int:
        cursor = self.db.execute("DELETE FROM jobs")
        self.db.commit()
        return cursor.rowcount
