from typing import Any

import yaml

from app.core.config import get_settings


def load_profile() -> dict[str, Any]:
    path = get_settings().PROFILE_PATH
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; copy profile.yaml.example to profile.yaml and edit it")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not data.get("name"):
        raise ValueError("profile.yaml needs at least a name")
    return dict(data)
