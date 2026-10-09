# JobApply

A local-first TUI for collecting job descriptions and generating evidence-based, AI-tailored PDF resumes.

The application never submits applications. Scraped descriptions, pasted descriptions, profile data, generated LaTeX, and PDFs stay local by default.

## License

JobApply is available under the **JobApply Personal Use License**. Personal,
educational, research, and internal non-commercial use are allowed. Offering
JobApply or a modified version as a hosted SaaS, API, paid product, or other
commercial service requires prior written permission. See `LICENSE` for the
full terms.

## Quick start

```bash
cd /path/to/job_apply
cp profile.example.json ~/.jobapply/profile.json
cp resume-template.example.tex ~/.jobapply/resume-template.tex
python3 -m pip install -e .
python3 -m jobapply tui
```

The first two commands create your private local profile and resume template.
They are not tracked by Git. The generated PDFs and job descriptions are also
kept locally.

## Docker

Build the image from the repository root:

```bash
docker build -t jobapply:local .
```

Prepare the private configuration on the host if you have not already:

```bash
mkdir -p ~/.jobapply
cp profile.example.json ~/.jobapply/profile.json
cp resume-template.example.tex ~/.jobapply/resume-template.tex
```

Run the interactive TUI with your profile, database, and generated PDFs mounted
outside the container:

```bash
docker run --rm -it \
  -e HOME=/data \
  -v "$HOME/.jobapply:/data/.jobapply" \
  -v "$PWD/generated-resumes:/data/generated-resumes" \
  jobapply:local tui
```

The equivalent Compose workflow is:

```bash
docker compose -f docker-compose.jobapply.yml build
docker compose -f docker-compose.jobapply.yml run --rm jobapply
```

The image includes Python, `pdflatex`, `pdftotext`, and `xclip`. Clipboard
access from inside a container depends on the host desktop's X11 permissions;
if `p` cannot access the clipboard, paste the description into a host-side
workflow or run the TUI directly on the host.

## Add your information

Edit `~/.jobapply/profile.json` and replace the example values:

```json
{
  "name": "Your Name",
  "email": "you@example.com",
  "linkedin": "https://www.linkedin.com/in/you",
  "github": "https://github.com/you",
  "headline": "Your professional headline",
  "summary": "A truthful summary of your experience.",
  "experience": [
    {
      "company": "Company",
      "dates": "2022 -- Present",
      "role": "Software Engineer",
      "bullets": ["A measurable accomplishment using technologies you actually used."],
      "technologies": "Python, PostgreSQL, Docker"
    }
  ],
  "skills": [["Programming", "Python, TypeScript, SQL"]]
}
```

Use only verifiable information. The generator ranks and rewrites your
existing evidence; it must not be used to invent employers, dates, metrics, or
skills.

To use an existing personal LaTeX resume instead, keep it outside the public
repository and configure its path in the TUI with `c`. It must contain these
markers:

```text
% JOBAPPLY:SUMMARY:START ... % JOBAPPLY:SUMMARY:END
% JOBAPPLY:SKILLS:START ... % JOBAPPLY:SKILLS:END
% JOBAPPLY:EXPERIENCE:START ... % JOBAPPLY:EXPERIENCE:END
```

## Generate From A Pasted Job

1. Copy the complete job description to your system clipboard.
2. Start the TUI with `python3 -m jobapply tui`.
3. Press `p` for **paste**.
4. Confirm the job title, company, location, and optional URL.
5. Select the new job and press `g` to generate the tailored resume.
6. Review the generated `.tex`, `.pdf`, and `application-answers.txt` files.

The PDF is written to `generated-resumes/<job-id>-<role>/` by default. The
description is stored in the local SQLite database at `~/.jobapply/jobs.db`.
Pasting requires `xclip`; install it with your operating system package
manager if the TUI reports that the clipboard is unavailable.

### Commure example

For a pasted Commure role such as **Software Engineer, Autonomous Revenue
Operations (Brazil)**, copy the job description, press `p`, enter `Commure` and
the role details, then select it and press `g`. With the private profile and
template used during development, the generated PDF was written to:

```text
generated-resumes/commure-autonomous-revenue-operations-brazil-software-engineer-autonomous-revenue-operations/tailored-resume.pdf
```

Professional experience is always rendered newest-first based on the start
month and year in each profile entry, regardless of the order returned by an AI
provider.

Press `c` before generating to configure:

- `Resume LaTeX template`: your private template path
- `Profile JSON`: your private profile path
- `GitHub username`: optional public repositories used as additional evidence
- `AI provider`: `none`, `openai`, `deepseek`, `openrouter`, `ollama`, `codex`, or `opencode`

With `none`, tailoring uses deterministic local matching. With an AI provider,
the job description, profile, and public GitHub metadata are sent to that
provider for ranking and wording. The result is still written locally for
review and falls back to local matching if the provider is unavailable.

For example, to use DeepSeek:

```bash
export DEEPSEEK_API_KEY=your-key
python3 -m jobapply tui
```

Then press `c`, set the provider to `deepseek`, and optionally set a model.

```bash
python3 -m jobapply search 'site:ashbyhq.com "AI Engineer" remote'
python3 -m jobapply jobs
python3 -m jobapply show 1
python3 -m jobapply status 1 interested
```

The database is stored at `~/.jobapply/jobs.db`. Override it with `JOBAPPLY_DB` or
`--db`. Search uses Google dorks first, then Bing and DuckDuckGo public HTML
results to find Ashby posting URLs, then
uses Ashby's public posting API to import the full job board. No credentials or
automatic applications are used.

## Commands

- `search [QUERY]`: discover Ashby boards from a search query and import their jobs
- `add BOARD`: import a known Ashby board URL or slug directly
- `jobs`: list saved jobs, with optional `--status`, `--query`, and `--limit`
- `show ID`: display the complete normalized job record and description
- `show IDS`: display one or more jobs; supports `1,3,4` and `1,2-5,8`
- `jobs --ids IDS`: list a selected set of jobs
- `status IDS STATUS`: set statuses for one or more jobs using ranges
- `delete IDS`: delete one or more jobs using ranges
- `reset --yes`: clear the local job database
- `tui`: open the interactive terminal interface
- `status ID STATUS`: set `new`, `interested`, `applied`, `ignored`, or `closed`
- `delete ID`: remove a saved job

Use `python3 -m jobapply --help` for all options.

The TUI stores scraper settings in `~/.jobapply/config.json`. Press `c` to
configure the query, recent-day window, board limit, concurrency, search-result
limit, and per-company limit. Press `r` to refresh listings using those values.

Imports keep at most 10 listings per company, preferring the newest published
roles. The TUI displays sequential row numbers; database IDs are internal.

Launch the TUI with:

```bash
python3 -m jobapply tui
```

Before generating your first resume, copy `profile.example.json` to
`~/.jobapply/profile.json` and edit it. Copy `resume-template.example.tex` to a
private template path, or configure an existing LaTeX resume in the TUI with `c`.

Use `r` to scrape configured listings, `p` to import a job description from the
clipboard, `Enter` for details, and `g` to generate and open a tailored PDF plus
show copy-paste answers. `/` filters, `Space` marks, `s` changes status, `d`
deletes, and `q` quits.

The base resume defaults to the safe example template. Generated LaTeX, PDF,
and application-answer files are written under
`generated-resumes/<job-id>-<role>/`. Generation is review-only: it does not
submit an application. `pdflatex` must be installed for PDF generation.

Generation can use the configured public GitHub profile as additional evidence.
Press `c` in the TUI to configure the username, local profile, template, and AI
provider. Public-source additions are evidence-based; the generator does not
invent experience that is not present in the profile, job data, or public
project metadata.

## AI providers

Set the provider in the TUI with `c`. `none` uses deterministic local ranking.
AI providers receive the job description and profile evidence and must return a
validated JSON tailoring plan. If a provider fails, local ranking is used.

- `openai`: set `OPENAI_API_KEY`
- `deepseek`: set `DEEPSEEK_API_KEY`
- `openrouter`: set `OPENROUTER_API_KEY`
- `ollama`: uses the local OpenAI-compatible Ollama endpoint
- `codex`: runs `codex exec`, or `JOBAPPLY_AI_COMMAND`
- `opencode`: runs `opencode run`, or `JOBAPPLY_AI_COMMAND`

For compatible hosted or local endpoints, set the optional base URL and model in
the TUI. AI output is never trusted as new evidence: experience bullets must
come from the local profile, while generated wording remains reviewable in the
output directory.

When search engines do not expose enough Ashby URLs, `search` scans up to 200
Ashby boards from the latest Common Crawl index and requests them concurrently.
Increase coverage with `--boards 1000`; tune network concurrency with
`--workers 20`.

For reliable Google results, configure a Google Programmable Search JSON API:

```bash
export GOOGLE_SEARCH_API_KEY=your-key
export GOOGLE_SEARCH_CSE_ID=your-search-engine-id
```

Brave Search API is also supported:

```bash
export BRAVE_SEARCH_API_KEY=your-key
```

For a self-hosted metasearch provider, configure SearXNG. Enable its JSON
format in the instance settings, then point the CLI at the instance:

```bash
export SEARXNG_URL=http://localhost:8080
python3 -m jobapply search 'site:ashbyhq.com "AI Engineer" remote'
```

SearXNG is queried first and can aggregate Google, Bing, Brave, and other
engines without putting their API keys in this CLI.

Start a local SearXNG instance with Docker:

```bash
docker compose -f docker-compose.searxng.yml up -d
curl 'http://localhost:8080/search?q=site%3Ajobs.ashbyhq.com%20AI%20Engineer&format=json'
```

Without API credentials, HTML search fallbacks may be rate-limited or return
zero results. A `504` from Common Crawl means its large index query timed out;
retry later or use one of the authenticated providers above.
