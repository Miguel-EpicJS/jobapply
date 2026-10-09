import curses
import subprocess
import textwrap
from uuid import uuid4

from .config import AppConfig
from .generation import generate_resume
from .models import Job
from .scraper import cap_per_company, published_within, scrape_query
from .storage import JobStore


STATUSES = ("new", "interested", "applied", "ignored", "closed")


def prompt(screen, label: str) -> str:
    height, width = screen.getmaxyx()
    screen.move(height - 1, 0)
    screen.clrtoeol()
    screen.addnstr(height - 1, 0, label, width - 1)
    curses.echo()
    value = screen.getstr(height - 1, min(len(label), width - 1), width - len(label) - 1).decode(errors="replace")
    curses.noecho()
    return value.strip()


def draw_header(screen, title: str, footer: str) -> None:
    height, width = screen.getmaxyx()
    if height < 2 or width < 2:
        return
    screen.attron(curses.A_REVERSE)
    screen.addnstr(0, 0, title.ljust(width - 1), width - 1)
    screen.attroff(curses.A_REVERSE)
    screen.addnstr(height - 1, 0, footer.ljust(width - 1), width - 1)


def draw_detail(screen, job) -> None:
    screen.clear()
    height, width = screen.getmaxyx()
    draw_header(screen, f"{job['title']} | {job['company']}", "Esc/b: back   q: quit")
    lines = [
        f"Status: {job['status']}",
        f"Location: {job['location']}",
        f"Published: {job['published_at']}",
        f"URL: {job['url']}",
        "",
        "Description:",
    ]
    description = job["description"] or "No description available."
    description = " ".join(description.replace("<", " <").split())
    description = __import__("re").sub(r"<[^>]+>", " ", description)
    lines.extend(textwrap.wrap(description, max(20, width - 2)))
    for index, line in enumerate(lines[: max(0, height - 2)], 1):
        screen.addnstr(index, 0, line, width - 1)
    screen.refresh()


def draw_answers(screen, job, pdf_path, questions) -> None:
    screen.clear()
    height, width = screen.getmaxyx()
    draw_header(screen, f"Generated: {job['title']}", "b/Esc: back   q: quit")
    lines = [f"TEX: {pdf_path.with_suffix('.tex')}", f"PDF: {pdf_path}", "", "Copy-paste answers:", ""]
    for index, question in enumerate(questions, 1):
        lines.extend([f"{index}. {question.title} ({'required' if question.required else 'optional'})", f"COPY: {question.answer}", ""])
    if not questions:
        lines.append("No custom application questions were exposed by Ashby.")
    for index, line in enumerate(lines[: max(0, height - 2)], 1):
        screen.addnstr(index, 0, line, width - 1)
    screen.refresh()


def configure(screen, config: AppConfig) -> None:
    values = (
        ("Query", "query", str),
        ("Recent days", "recent_days", int),
        ("Board limit", "board_limit", int),
        ("Workers", "workers", int),
        ("Search result limit", "search_limit", int),
        ("Per-company limit", "per_company", int),
        ("Resume LaTeX template", "resume_path", str),
        ("Application output directory", "output_dir", str),
        ("GitHub username", "github_username", str),
        ("Profile JSON", "profile_path", str),
        ("AI provider (none/openai/deepseek/openrouter/ollama/codex/opencode)", "ai_provider", str),
        ("AI model", "ai_model", str),
        ("AI base URL (optional)", "ai_base_url", str),
    )
    for label, key, converter in values:
        value = prompt(screen, f"{label} [{getattr(config, key)}]: ")
        if value:
            try:
                setattr(config, key, converter(value))
            except ValueError:
                pass
    config.save()


def paste_job(screen) -> Job | None:
    """Create a local job from clipboard text without sending it anywhere."""
    try:
        description = subprocess.run(["xclip", "-selection", "clipboard", "-o"], check=True, capture_output=True, text=True).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    if not description:
        return None
    title = prompt(screen, "Job title: ") or "Pasted job description"
    company = prompt(screen, "Company: ") or "Unknown company"
    location = prompt(screen, "Location (optional): ")
    url = prompt(screen, "URL (optional): ")
    return Job("clipboard", str(uuid4()), title, company, location, description, url)


def run(screen, store: JobStore, config: AppConfig) -> None:
    curses.curs_set(0)
    screen.keypad(True)
    query = ""
    selected = 0
    detail = None
    marked = set()
    message = ""
    while True:
        if isinstance(detail, tuple):
            job, pdf_path, questions = detail
            draw_answers(screen, job, pdf_path, questions)
            key = screen.getch()
            if key in (27, ord("b")):
                detail = None
            elif key in (ord("q"), ord("Q")):
                return
            continue
        if detail is not None:
            draw_detail(screen, detail)
            key = screen.getch()
            if key in (27, ord("b")):
                detail = None
            elif key in (ord("q"), ord("Q")):
                return
            continue

        rows = store.list(query=query or None, limit=500)
        selected = min(selected, max(0, len(rows) - 1))
        screen.clear()
        draw_header(screen, f"JobApply TUI  |  {len(rows)} jobs" + (f"  |  filter: {query}" if query else ""),
                    "r: scrape  p: paste  c: configure  g: generate  Up/Down/j/k: move  Enter: details  /: filter  s: status  d: delete  Space: mark  q: quit")
        height, width = screen.getmaxyx()
        visible = max(1, height - 2)
        top = max(0, selected - visible + 1)
        for index, job in enumerate(rows[top : top + visible], top):
            marker = "*" if job["id"] in marked else " "
            line = f"{marker} {index + 1:>3} [{job['status']:<10}] {job['title']} | {job['company']} | {job['location']}"
            if index == selected:
                screen.attron(curses.A_REVERSE)
            screen.addnstr(index - top + 1, 0, line, width - 1)
            if index == selected:
                screen.attroff(curses.A_REVERSE)
        if message and height > 2:
            screen.addnstr(height - 2, 0, message, width - 1)
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), ord("Q")):
            return
        if key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(max(0, len(rows) - 1), selected + 1)
        elif key in (curses.KEY_ENTER, 10, 13) and rows:
            detail = rows[selected]
        elif key in (ord("g"), ord("G")) and rows:
            try:
                pdf_path, questions = generate_resume(rows[selected], config.resume_path, config.output_dir, config.github_username, config.profile_path, config.ai_provider, config.ai_model, config.ai_base_url)
                subprocess.Popen(["xdg-open", str(pdf_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                detail = (rows[selected], pdf_path, questions)
            except Exception as error:
                message = f"Generation failed: {error}"
        elif key == ord(" ") and rows:
            job_id = rows[selected]["id"]
            marked.remove(job_id) if job_id in marked else marked.add(job_id)
        elif key == ord("/"):
            query = prompt(screen, "Filter: ")
            selected = 0
        elif key in (ord("r"), ord("R")):
            try:
                jobs, urls = scrape_query(config.query, config.search_limit, config.recent_days,
                                          config.board_limit, config.workers, config.per_company)
                added, updated = store.upsert_many(jobs)
                message = f"Refresh: {len(jobs)} jobs from {len(urls)} boards; added {added}, updated {updated}."
            except Exception as error:
                message = f"Refresh failed: {error}"
        elif key in (ord("p"), ord("P")):
            pasted = paste_job(screen)
            if pasted is None:
                message = "Clipboard is empty or xclip is unavailable."
            else:
                store.upsert_many([pasted])
                message = f"Added pasted description: {pasted.title}."
        elif key in (ord("c"), ord("C")):
            configure(screen, config)
            message = "Configuration saved to ~/.jobapply/config.json. Press r to refresh."
        elif key in (ord("s"), ord("S")) and rows:
            value = prompt(screen, "Status (new/interested/applied/ignored/closed): ")
            if value in STATUSES:
                ids = marked or {rows[selected]["id"]}
                for job_id in ids:
                    store.set_status(job_id, value)
                marked.clear()
        elif key in (ord("d"), ord("D")) and rows:
            ids = marked or {rows[selected]["id"]}
            if prompt(screen, f"Delete {len(ids)} job(s)? [y/N] ").lower() == "y":
                for job_id in ids:
                    store.delete(job_id)
                marked.clear()
                selected = max(0, selected - 1)


def start(store: JobStore, config: AppConfig | None = None) -> None:
    curses.wrapper(run, store, config or AppConfig.load())
