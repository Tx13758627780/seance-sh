"""All knobs are environment variables, so the shell hook stays tiny."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def state_dir() -> Path:
    base = os.environ.get("SEANCE_HOME") or os.path.join(
        os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "seance"
    )
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    host: str = field(default_factory=lambda: os.environ.get("SEANCE_HOST") or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434")
    model: str = field(default_factory=lambda: os.environ.get("SEANCE_MODEL", "gemma3:4b"))
    ofrenda_model: str = field(default_factory=lambda: os.environ.get("SEANCE_OFRENDA_MODEL") or os.environ.get("SEANCE_MODEL", "gemma3:4b"))
    timeout: float = field(default_factory=lambda: _float("SEANCE_TIMEOUT", 12.0))
    glitch: float = field(default_factory=lambda: _float("SEANCE_GLITCH", 0.25))
    type_delay: float = field(default_factory=lambda: _float("SEANCE_TYPE_DELAY", 0.012))
    rate: float = field(default_factory=lambda: _float("SEANCE_RATE", 1.0))
    memory: int = field(default_factory=lambda: int(_float("SEANCE_MEMORY", 8)))
    session: str = field(default_factory=lambda: os.environ.get("SEANCE_SESSION", "default"))

    def __post_init__(self) -> None:
        if not self.host.startswith("http"):
            self.host = "http://" + self.host
        self.host = self.host.rstrip("/")
