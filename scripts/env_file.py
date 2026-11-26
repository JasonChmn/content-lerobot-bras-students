"""Loads the repo's .env (KEY=value lines) into os.environ."""
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load() -> None:
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        value = value.split(" #", 1)[0].strip().strip("\"'")  # value  # comment
        if value:
            os.environ.setdefault(key, os.path.expanduser(value))
