import argparse
import os
import re
import sys
from html import unescape
from pathlib import Path

from .scraper import cap_per_company, published_within, scrape_board, scrape_query
from .selection import parse_id_ranges
from .storage import JobStore
from .config import AppConfig
from .tui import start as start_tui


STATUSES = {"new", "interested", "applied", "ignored", "closed"}


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", unescape(value or ""))
    return re.sub(r"\s+", " ", value).strip()


def default_db() -> str:
    return os.environ.get("JOBAPPLY_DB", "~/.jobapply/jobs.db")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobapply", description="Discover and organize job applications")
    parser.add_argument("--db", default=default_db(), help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Find Ashby jobs via a search query")
    search.add_argument("query", nargs="?", default='site:ashbyhq.com "AI Engineer" remote')
    search.add_argument("--limit", type=int, default=20, help="Maximum search results to inspect")
    search.add_argument("--boards", type=int, default=200, help="Maximum Ashby boards to scan when search engines return no URLs")
    search.add_argument("--workers", type=int, default=12, help="Concurrent Ashby board requests")
    search.add_argument("--all", action="store_true", help="Include jobs older than 14 days")
    add = sub.add_parser("add", help="Import an Ashby board URL or slug")
    add.add_argument("board", help="For example: https://jobs.ashbyhq.com/linear or linear")
    add.add_argument("--all", action="store_true", help="Include jobs older than 14 days")
    listing = sub.add_parser("jobs", help="List saved jobs")
    listing.add_argument("--status", choices=sorted(STATUSES))
    listing.add_argument("--query")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--recent", action="store_true", help="Show only jobs published in the last 14 days")
    listing.add_argument("--ids", help="Restrict output to IDs or ranges, for example: 1,3,5-7")
    show = sub.add_parser("show", help="Show one job")
    show.add_argument("ids", help="IDs or ranges, for example: 1,3,5-7")
    status = sub.add_parser("status", help="Change a job's workflow status")
    status.add_argument("ids", help="IDs or ranges, for example: 1,3,5-7")
    status.add_argument("status", choices=sorted(STATUSES))
    delete = sub.add_parser("delete", help="Delete one saved job")
    delete.add_argument("ids", help="IDs or ranges, for example: 1,3,5-7")
    reset = sub.add_parser("reset", help="Delete all saved jobs")
    reset.add_argument("--yes", action="store_true", help="Skip confirmation")
    sub.add_parser("tui", help="Open the interactive terminal interface")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    store = JobStore(args.db)
    config = AppConfig.load()
    try:
        if args.command == "search":
            jobs, urls = scrape_query(args.query, args.limit, None if args.all else 14, args.boards, args.workers, config.per_company)
            added, updated = store.upsert_many(jobs)
            window = "all time" if args.all else "last 14 days"
            print(f"Found {len(jobs)} jobs from {len(urls)} Ashby boards ({window}); added {added}, updated {updated}.")
            for job in store.list(query=args.query, limit=10):
                print(f"{job['id']:>4}  {job['title']}  |  {job['company']}  |  {job['location']}")
        elif args.command == "add":
            board = args.board if args.board.startswith("http") else f"https://jobs.ashbyhq.com/{args.board}"
            jobs = scrape_board(board)
            if not args.all:
                jobs = published_within(jobs, 14)
            jobs = cap_per_company(jobs)
            added, updated = store.upsert_many(jobs)
            window = "all time" if args.all else "last 14 days"
            print(f"Imported {len(jobs)} jobs ({window}); added {added}, updated {updated}.")
        elif args.command == "jobs":
            rows = store.list(args.status, args.query, args.limit * 4 if args.recent else args.limit)
            if args.recent:
                from datetime import datetime, timedelta, timezone
                cutoff = datetime.now(timezone.utc) - timedelta(days=14)
                rows = [row for row in rows if row["published_at"] and _is_recent(row["published_at"], cutoff)][:args.limit]
            if args.ids:
                selected = set(parse_id_ranges(args.ids))
                rows = [row for row in rows if row["id"] in selected]
            for job in rows:
                print(f"{job['id']:>4} [{job['status']:<10}] {job['title']} | {job['company']} | {job['location']}")
        elif args.command == "show":
            for index, job_id in enumerate(parse_id_ranges(args.ids)):
                job = store.get(job_id)
                if not job:
                    raise SystemExit(f"Job {job_id} not found")
                if index:
                    print("\n" + "=" * 72 + "\n")
                for key in ("id", "status", "title", "company", "location", "employment_type", "department", "team", "published_at", "url"):
                    print(f"{key.replace('_', ' ').title()}: {job[key]}")
                print("\nDescription:\n" + clean_text(job["description"]))
        elif args.command == "status":
            for job_id in parse_id_ranges(args.ids):
                if not store.set_status(job_id, args.status):
                    raise SystemExit(f"Job {job_id} not found")
            print(f"Jobs {args.ids} marked {args.status}.")
        elif args.command == "delete":
            deleted = 0
            for job_id in parse_id_ranges(args.ids):
                if store.delete(job_id):
                    deleted += 1
            print(f"Deleted {deleted} job(s) from selection {args.ids}.")
        elif args.command == "reset":
            if not args.yes and input("Delete every saved job? [y/N] ").lower() != "y":
                print("Reset cancelled.")
                return
            print(f"Deleted {store.reset()} job(s).")
        elif args.command == "tui":
            start_tui(store, config)
    finally:
        store.close()


def _is_recent(value: str, cutoff) -> bool:
    from datetime import datetime
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if published.tzinfo is None:
            published = published.replace(tzinfo=cutoff.tzinfo)
        return published >= cutoff
    except ValueError:
        return False


if __name__ == "__main__":
    main(sys.argv[1:])
