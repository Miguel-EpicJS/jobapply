from dataclasses import dataclass
from typing import Any


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    url: str = ""
    employment_type: str = ""
    department: str = ""
    team: str = ""
    published_at: str = ""
    source_query: str = ""

    @classmethod
    def from_ashby(cls, raw: dict[str, Any], query: str = "") -> "Job":
        job_url = raw.get("jobUrl") or raw.get("applyUrl") or ""
        return cls(
            source="ashby",
            external_id=str(raw.get("id") or job_url),
            title=str(raw.get("title") or "Untitled role").strip(),
            company=str(raw.get("companyName") or raw.get("organizationName") or "").strip(),
            location=str(raw.get("location") or "").strip(),
            description=str(raw.get("descriptionHtml") or raw.get("description") or "").strip(),
            url=job_url,
            employment_type=str(raw.get("employmentType") or "").strip(),
            department=str(raw.get("department") or "").strip(),
            team=str(raw.get("team") or "").strip(),
            published_at=str(raw.get("publishedAt") or "").strip(),
            source_query=query,
        )
