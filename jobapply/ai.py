import json
import os
import shlex
import subprocess
from urllib.request import Request, urlopen


PROVIDER_DEFAULTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "ollama": "http://localhost:11434/v1/chat/completions",
}


def _prompt(job: dict, profile: dict) -> str:
    evidence = {
        "summary": profile.get("summary", ""),
        "experience": profile.get("experience", []),
        "skills": profile.get("skills", []),
        "projects": profile.get("projects", []),
    }
    return f"""Tailor a resume using only the candidate evidence below. Never invent employers, dates, metrics, technologies, titles, or experience. Rank existing bullets and skills for the job. Return JSON only with keys summary, experience, skills. Keep every experience bullet verbatim from the evidence.

JOB:
{job.get('title', '')} at {job.get('company', '')}
{job.get('description', '')}

CANDIDATE EVIDENCE:
{json.dumps(evidence, ensure_ascii=False)}

JSON shape:
{{"summary": "...", "experience": [{{"company": "...", "dates": "...", "role": "...", "bullets": ["..."], "technologies": "..."}}], "skills": [["category", "comma-separated skills"]]}}"""


def _api_call(endpoint: str, api_key: str, model: str, prompt: str) -> str:
    payload = json.dumps({"model": model, "temperature": 0.2, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": "You are an evidence-preserving resume editor."}, {"role": "user", "content": prompt}]}).encode()
    request = Request(endpoint, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
    with urlopen(request, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8", errors="replace"))
    return data["choices"][0]["message"]["content"]


def _cli_call(command: str, prompt: str) -> str:
    result = subprocess.run(shlex.split(command), input=prompt, text=True, capture_output=True, timeout=120, check=True)
    return result.stdout


def tailor(job: dict, profile: dict, provider: str, model: str = "", base_url: str = "") -> dict | None:
    """Ask an optional provider for evidence-preserving ordering and wording."""
    if not provider or provider == "none":
        return None
    prompt = _prompt(job, profile)
    try:
        if provider in PROVIDER_DEFAULTS:
            key = os.environ.get({"openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY", "openrouter": "OPENROUTER_API_KEY", "ollama": "OLLAMA_API_KEY"}[provider], "")
            if provider != "ollama" and not key:
                return None
            raw = _api_call(base_url or PROVIDER_DEFAULTS[provider], key, model or ("deepseek-chat" if provider == "deepseek" else "llama3.2" if provider == "ollama" else "gpt-4o-mini"), prompt)
        elif provider in {"codex", "opencode", "command"}:
            command = os.environ.get("JOBAPPLY_AI_COMMAND", "")
            if not command:
                command = "codex exec" if provider == "codex" else "opencode run" if provider == "opencode" else ""
            if not command:
                return None
            raw = _cli_call(command, prompt)
        else:
            return None
        result = json.loads(raw.strip().strip("`").replace("json\n", "", 1))
        if not isinstance(result, dict) or not isinstance(result.get("experience"), list) or not isinstance(result.get("skills"), list):
            return None
        return result
    except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
