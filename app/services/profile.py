from typing import Any

import yaml

from app.core.config import get_settings


def load_profile() -> dict[str, Any]:
    s = get_settings()
    if s.PROFILE_YAML:
        data = yaml.safe_load(s.PROFILE_YAML) or {}
    elif s.PROFILE_PATH.exists():
        data = yaml.safe_load(s.PROFILE_PATH.read_text(encoding="utf-8")) or {}
    else:
        raise FileNotFoundError(f"{s.PROFILE_PATH} not found; copy profile.yaml.example to profile.yaml or set PROFILE_YAML")
    if not data.get("name"):
        raise ValueError("profile.yaml needs at least a name")
    return dict(data)
