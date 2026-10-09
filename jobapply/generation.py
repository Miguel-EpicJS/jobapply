import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import Job
from .profile import load_profile
from .ai import tailor


GRAPHQL = """query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) {
  jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) {
    applicationForm { sections { fieldEntries { field isRequired descriptionHtml isHidden } } }
  }
}"""


@dataclass
class Question:
    title: str
    field_type: str
    required: bool
    answer: str
    description: str = ""


def job_value(job, key: str) -> str:
    try:
        return str(job[key] or "")
    except (KeyError, TypeError):
        return str(getattr(job, key, "") or "")


def resume_text(path: str | Path) -> str:
    result = subprocess.run(["pdftotext", "-layout", str(Path(path).expanduser()), "-"], check=True, capture_output=True, text=True)
    return result.stdout.replace("\u00a0", " ")


def github_evidence(username: str) -> tuple[str, list[dict]]:
    if not username:
        return "", []
    request = Request(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated", headers={"User-Agent": "jobapply/0.1", "Accept": "application/vnd.github+json"})
    try:
        with urlopen(request, timeout=20) as response:
            repos = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError, json.JSONDecodeError):
        return "", []
    if not isinstance(repos, list):
        return "", []
    evidence = "\n".join(f"{repo.get('name', '')} {repo.get('language') or ''} {repo.get('description') or ''}" for repo in repos)
    return evidence, repos


def clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def ashby_application_url(url: str) -> str:
    return url.rstrip("/") + "/application" if not url.rstrip("/").endswith("/application") else url


def _ashby_parts(url: str) -> tuple[str, str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Not an Ashby job URL")
    return parsed.scheme + "://" + parsed.netloc, parts[0], parts[1]


def fetch_questions(url: str) -> list[dict]:
    host, company, posting_id = _ashby_parts(url)
    endpoint = f"{host}/api/non-user-graphql?op=ApiJobPosting"
    payload = json.dumps({"operationName": "ApiJobPosting", "variables": {"organizationHostedJobsPageName": company, "jobPostingId": posting_id}, "query": GRAPHQL}).encode()
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "jobapply/0.1"})
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    fields = []
    for section in (data.get("data", {}).get("jobPosting", {}).get("applicationForm", {}) or {}).get("sections", []):
        for entry in section.get("fieldEntries", []):
            field = entry.get("field") or {}
            if entry.get("isHidden") or field.get("path", "").startswith("_systemfield_"):
                continue
            fields.append({"title": field.get("title") or field.get("humanReadablePath") or field.get("path", "Question"), "type": field.get("type", "String"), "required": bool(entry.get("isRequired")), "description": clean_html(entry.get("descriptionHtml", ""))})
    return fields


def _answer(title: str, job: Job, source: str, profile: dict | None = None) -> str:
    lower = title.lower()
    profile = profile or {}
    if "linkedin" in lower:
        match = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s]+", source, re.I)
        return (match.group(0) if match else profile.get("linkedin")) or "[Add your LinkedIn URL]"
    if "github" in lower:
        match = re.search(r"(?:https?://)?github\.com/[^\s]+", source, re.I)
        return (match.group(0) if match else profile.get("github")) or "[Add your GitHub URL]"
    if "phone" in lower or "whatsapp" in lower:
        match = re.search(r"(?:\+?\d[\d ()-]{8,}\d)", source)
        return match.group(0).strip() if match else "[Add your phone number]"
    if "salary" in lower or "compensation" in lower:
        return "[Enter your target compensation and currency]"
    if "why" in lower or "interest" in lower or "motivat" in lower:
        return f"I am interested in {job_value(job, 'title')} because it matches my documented experience and the role's goals."
    return "[Review and complete this answer with your specific, truthful details]"


def generate_questions(job: Job, source: str, profile: dict | None = None) -> list[Question]:
    try:
        fields = fetch_questions(ashby_application_url(job.url))
    except (OSError, ValueError, json.JSONDecodeError):
        fields = []
    return [Question(f["title"], f["type"], f["required"], _answer(f["title"], job, source, profile), f["description"]) for f in fields]


def _latex(value: str) -> str:
    replacements = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}"}
    return "".join(replacements.get(character, character) for character in value)


def _job_words(description: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.-]{3,}", clean_html(description).lower()))


def _experience_date(entry: dict) -> tuple[int, int]:
    months = {name: index for index, name in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"), 1)}
    dates = str(entry.get("dates", "")).lower()
    year = re.search(r"\b(19|20)\d{2}\b", dates)
    month = next((number for name, number in months.items() if name in dates), 0)
    return (int(year.group(0)) if year else 0, month)


def _tailored_experience(description: str, profile: dict) -> str:
    words = _job_words(description)
    blocks = []
    for entry in sorted(profile["experience"], key=_experience_date, reverse=True):
        bullets = sorted(entry.get("bullets", []), key=lambda bullet: -len(set(re.findall(r"[a-z0-9+#.-]{3,}", bullet.lower())) & words))
        blocks.extend([rf"\job{{{_latex(entry['company'])}}}{{{_latex(entry.get('dates', ''))}}}{{{_latex(entry.get('role', ''))}}}{{}}", r"\begin{itemize}", *[rf"  \item {_latex(bullet)}" for bullet in bullets[:6]], r"\end{itemize}", rf"\textbf{{Technologies:}} {_latex(entry.get('technologies', ''))}", r""])
    return "\n".join(blocks).rstrip()


def _tailored_skills(description: str, profile: dict) -> str:
    words = _job_words(description)
    skills = sorted(profile["skills"], key=lambda skill: -len(set(re.findall(r"[a-z0-9+#.-]{3,}", skill[1].lower())) & words))
    return "\n".join(rf"\textbf{{{_latex(name)}:}} {_latex(value)}\\" for name, value in skills)


def _replace_template_block(template: str, name: str, content: str) -> str:
    pattern = rf"(% JOBAPPLY:{name}:START\n).*?(% JOBAPPLY:{name}:END)"
    rendered, count = re.subn(pattern, lambda match: match.group(1) + content + "\n" + match.group(2), template, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"LaTeX template is missing JOBAPPLY:{name} markers")
    return rendered


def render_resume(template: str, job: Job, profile: dict | None = None) -> str:
    profile = profile or {"summary": "Your summary", "experience": [], "skills": []}
    summary = profile["summary"] + f" Targeted for {job_value(job, 'title') or 'this role'} roles through evidence from the job description."
    rendered = _replace_template_block(template, "SUMMARY", _latex(summary))
    rendered = _replace_template_block(rendered, "SKILLS", _tailored_skills(job_value(job, "description"), profile))
    return _replace_template_block(rendered, "EXPERIENCE", _tailored_experience(job_value(job, "description"), profile))


def _source_text(path: str | Path) -> str:
    source_path = Path(path).expanduser()
    return source_path.read_text(encoding="utf-8") if source_path.suffix.lower() == ".tex" else resume_text(source_path)


def _compile_latex(tex_path: Path) -> Path:
    try:
        for _ in range(2):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name], cwd=tex_path.parent, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise RuntimeError("pdflatex is required to generate resume PDFs") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"LaTeX compilation failed: {(error.stdout or '')[-1200:]}") from error
    return tex_path.with_suffix(".pdf")


def generate_resume(job: Job, source_path: str | Path, output_dir: str | Path, github_username: str = "", profile_path: str | Path = "~/.jobapply/profile.json", ai_provider: str = "none", ai_model: str = "", ai_base_url: str = "") -> tuple[Path, list[Question]]:
    profile = load_profile(profile_path)
    _, repositories = github_evidence(github_username)
    profile = {**profile, "projects": [
        {"name": repo.get("name", ""), "description": repo.get("description") or "", "language": repo.get("language") or ""}
        for repo in repositories if repo.get("name")
    ]}
    tailored = tailor(job, profile, ai_provider, ai_model, ai_base_url)
    if tailored:
        profile = {**profile, **tailored}
    template_path = Path(source_path).expanduser()
    output = Path(output_dir).expanduser() / f"{job_value(job, 'id') or job_value(job, 'external_id')}-{re.sub(r'[^a-z0-9]+', '-', job_value(job, 'title').lower()).strip('-')}"
    output.mkdir(parents=True, exist_ok=True)
    tex_path = output / "tailored-resume.tex"
    tex_path.write_text(render_resume(template_path.read_text(encoding="utf-8"), job, profile), encoding="utf-8")
    pdf_path = _compile_latex(tex_path)
    questions = generate_questions(type("JobView", (), {"url": job_value(job, "url"), "title": job_value(job, "title")})(), _source_text(template_path), profile)
    (output / "application-answers.txt").write_text(format_questions(questions), encoding="utf-8")
    return pdf_path, questions


def format_questions(questions: list[Question]) -> str:
    if not questions:
        return "No custom application questions were exposed by the public job form API.\n"
    return "\n\n".join(f"{index}. {question.title} ({'required' if question.required else 'optional'})\nCOPY: {question.answer}" for index, question in enumerate(questions, 1)) + "\n"
