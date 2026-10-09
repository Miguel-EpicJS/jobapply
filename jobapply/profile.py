import json
from pathlib import Path
from typing import Any


REQUIRED_KEYS = {"name", "email", "headline", "summary", "experience", "skills"}


def load_profile(path: str | Path) -> dict[str, Any]:
    profile_path = Path(path).expanduser()
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Profile not found at {profile_path}. Copy profile.example.json there and edit it."
        )
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read profile {profile_path}: {error}") from error
    missing = REQUIRED_KEYS - profile.keys()
    if missing:
        raise ValueError(f"Profile is missing required keys: {', '.join(sorted(missing))}")
    if not isinstance(profile["experience"], list) or not isinstance(profile["skills"], list):
        raise ValueError("Profile experience and skills must be lists")
    return profile
