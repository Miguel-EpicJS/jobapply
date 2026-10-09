import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from .models import Job


USER_AGENT = "jobapply/0.1 (+local CLI)"


def fetch(url: str, timeout: int = 20) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def extract_ashby_urls(html: str) -> list[str]:
    """Extract direct Ashby posting/board URLs from search-provider HTML."""
    html = unescape(html).replace(r"\/", "/")
    links = re.findall(r"https?://(?:jobs\.)?ashbyhq\.com[^\s\"'<>\\?&]+(?:\?[^\s\"'<>\\]+)?", html, flags=re.I)
    result = []
    for link in links:
        link = unquote(link).rstrip(".,;)")
        parsed = urlparse(link)
        if parsed.netloc.lower() not in {"jobs.ashbyhq.com", "jobs.ashby.com"}:
            continue
        clean = f"https://jobs.ashbyhq.com{parsed.path}".rstrip("/")
        if clean not in result:
            result.append(clean)
    return result


def api_search_urls(query: str, limit: int) -> list[str]:
    """Use paid/provider APIs when credentials are explicitly configured."""
    result = []
    searxng_url = os.environ.get("SEARXNG_URL")
    if searxng_url:
        try:
            endpoint = searxng_url.rstrip("/") + "/search?" + f"q={quote_plus(query)}&format=json"
            payload = fetch_json(endpoint, headers={"Accept": "application/json"})
            for item in payload.get("results", []):
                result.extend(extract_ashby_urls(item.get("url", "")))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    result = list(dict.fromkeys(result))[:limit]
    if len(result) >= limit:
        return result
    google_key = os.environ.get("GOOGLE_SEARCH_API_KEY")
    google_cse = os.environ.get("GOOGLE_SEARCH_CSE_ID")
    if google_key and google_cse:
        try:
            payload = fetch_json(
                "https://www.googleapis.com/customsearch/v1?" +
                f"key={quote_plus(google_key)}&cx={quote_plus(google_cse)}&num=10&q={quote_plus(query)}"
            )
            for item in payload.get("items", []):
                result.extend(extract_ashby_urls(item.get("link", "")))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if brave_key:
        try:
            payload = fetch_json(
                "https://api.search.brave.com/res/v1/web/search?" +
                f"count={min(limit, 20)}&q={quote_plus(query)}",
                headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
            )
            for item in payload.get("web", {}).get("results", []):
                result.extend(extract_ashby_urls(item.get("url", "")))
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return list(dict.fromkeys(result))[:limit]


def discover_ashby_urls(query: str, limit: int = 20) -> list[str]:
    # Google is the intended provider for Google dorks. Some environments
    # block one or more providers, so failures and empty result pages fall
    # through to independent HTML endpoints.
    search_query = query.replace("site:ashbyhq.com", "site:jobs.ashbyhq.com")
    providers = (
        f"https://www.google.com/search?num={limit}&q={quote_plus(search_query)}",
        f"https://www.bing.com/search?count={limit}&q={quote_plus(search_query)}",
        f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}",
    )
    result = api_search_urls(search_query, limit)
    if len(result) >= limit:
        return result
    for provider in providers:
        try:
            result.extend(extract_ashby_urls(fetch(provider)))
        except OSError:
            continue
        result = list(dict.fromkeys(result))
        if len(result) >= limit:
            break
    return result[:limit]


def discover_ashby_boards(limit: int = 50) -> list[str]:
    """Discover board slugs from the latest Common Crawl URL index."""
    try:
        collections = json.loads(fetch("https://index.commoncrawl.org/collinfo.json"))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    payload = ""
    for collection in collections[:5]:
        for _ in range(2):
            try:
                # Keep the request broad: some Common Crawl index gateways time
                # out when filter/collapse parameters are combined with this large domain.
                payload = fetch(collection["cdx-api"] + "?url=jobs.ashbyhq.com/*&output=json", timeout=90)
                break
            except (OSError, KeyError):
                continue
        if payload:
            break
    if not payload:
        return []
    boards = []
    for line in payload.splitlines():
        try:
            url = json.loads(line).get("url", "")
        except json.JSONDecodeError:
            continue
        parts = [part for part in urlparse(url).path.split("/") if part]
        if not parts or parts[0].lower() in {"job", "jobs"}:
            continue
        board = f"https://jobs.ashbyhq.com/{parts[0]}"
        if board not in boards:
            boards.append(board)
        if len(boards) >= limit:
            break
    return boards


def job_matches_query(job: Job, query: str) -> bool:
    text = f"{job.title} {job.description} {job.location}".lower()
    phrases = re.findall(r'"([^"]+)"', query.lower())
    if phrases and not any(phrase in text for phrase in phrases):
        return False
    terms = re.findall(r"[a-z0-9+#.-]+", re.sub(r"site:\S+", "", query.lower()))
    terms = [term for term in terms if term not in {"remote", "and", "or"}]
    return all(term in text for term in terms if term not in phrases)


def board_slug(url: str) -> str | None:
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[0] if parts else None


def fetch_board(url: str, query: str = "") -> list[Job]:
    slug = board_slug(url)
    if not slug:
        return []
    payload = json.loads(fetch(f"https://api.ashbyhq.com/posting-api/job-board/{quote_plus(slug)}"))
    raw_jobs = payload.get("jobs", payload if isinstance(payload, list) else [])
    jobs = [Job.from_ashby(raw, query) for raw in raw_jobs if isinstance(raw, dict)]
    # The public board response often omits the company name; the board slug is
    # still more useful than an empty value in the local index.
    for job in jobs:
        if not job.company:
            job.company = slug.replace("-", " ").title()
    return jobs


def scrape_board(url: str) -> list[Job]:
    return fetch_board(url, query=url)


def published_within(jobs: list[Job], days: int = 14, now: datetime | None = None) -> list[Job]:
    """Keep jobs with a valid publishedAt timestamp in the recent window."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    recent = []
    for job in jobs:
        try:
            published = datetime.fromisoformat(job.published_at.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        if published >= cutoff:
            recent.append(job)
    return recent


def cap_per_company(jobs: list[Job], maximum: int = 10) -> list[Job]:
    """Keep the newest listings while preventing one company dominating results."""
    counts: dict[str, int] = {}
    result = []
    ordered = sorted(jobs, key=lambda job: job.published_at or "", reverse=True)
    for job in ordered:
        company = job.company.lower().strip() or "unknown"
        if counts.get(company, 0) >= maximum:
            continue
        counts[company] = counts.get(company, 0) + 1
        result.append(job)
    return result


def scrape_query(
    query: str,
    limit: int = 20,
    days: int | None = 14,
    board_limit: int = 200,
    workers: int = 12,
    per_company: int = 10,
) -> tuple[list[Job], list[str]]:
    urls = discover_ashby_urls(query, limit)
    from_search = bool(urls)
    if not urls:
        urls = discover_ashby_boards(board_limit)
    jobs: list[Job] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        pending = {executor.submit(fetch_board, url, query): url for url in urls}
        for future in as_completed(pending):
            try:
                jobs.extend(future.result())
            except (OSError, ValueError, json.JSONDecodeError):
                continue
    if days is not None:
        jobs = published_within(jobs, days)
    if not from_search:
        jobs = [job for job in jobs if job_matches_query(job, query)]
    jobs = cap_per_company(jobs, per_company)
    unique = {f"{job.source}:{job.external_id}": job for job in jobs}
    return list(unique.values()), urls
