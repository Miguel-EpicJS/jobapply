import json
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AppConfig:
    query: str = 'site:ashbyhq.com "AI Engineer" remote'
    recent_days: int = 14
    board_limit: int = 200
    workers: int = 12
    search_limit: int = 20
    per_company: int = 10
    resume_path: str = str(PROJECT_ROOT / "resume-template.example.tex")
    output_dir: str = str(PROJECT_ROOT / "generated-resumes")
    github_username: str = "Miguel-EpicJS"
    profile_path: str = "~/.jobapply/profile.json"
    ai_provider: str = "none"
    ai_model: str = ""
    ai_base_url: str = ""

    @classmethod
    def load(cls, path: str | Path = "~/.jobapply/config.json") -> "AppConfig":
        file_path = Path(path).expanduser()
        if not file_path.exists():
            return cls()
        try:
            values = json.loads(file_path.read_text())
            config = cls(**{key: values[key] for key in asdict(cls()) if key in values})
            # Migrate configurations created before LaTeX templates became the source.
            if Path(config.resume_path).suffix.lower() == ".pdf":
                config.resume_path = cls().resume_path
            if config.output_dir == "~/.jobapply/applications":
                config.output_dir = cls().output_dir
            return config
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path: str | Path = "~/.jobapply/config.json") -> None:
        file_path = Path(path).expanduser()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(asdict(self), indent=2) + "\n")
