"""The haunting memory: what the ghost remembers about tonight's session,
plus a long-lived graveyard of everything that died (for the ofrenda).

Everything lives in plain JSONL under ~/.local/state/seance/. Nothing leaves
the machine, and obvious secrets are redacted before they are even written."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Iterator

from .config import state_dir

SECRET_PATTERNS = [
    # KEY=value style env assignments with scary names
    (re.compile(r"\b([A-Z0-9_]*(TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|APIKEY|ACCESS_KEY)[A-Z0-9_]*)=(\S+)", re.I), r"\1=<redacted>"),
    # --password=foo / --token foo
    (re.compile(r"(--?(?:password|passwd|token|secret|api-key|apikey)[= ])(\S+)", re.I), r"\1<redacted>"),
    # Authorization headers
    (re.compile(r"(Authorization:\s*(?:Bearer|Basic|token)\s+)\S+", re.I), r"\1<redacted>"),
    # URLs with user:pass@
    (re.compile(r"(\w+://[^/\s:@]+:)[^@\s]+@"), r"\1<redacted>@"),
    # well known token shapes
    (re.compile(r"\b(ghp|gho|ghs|github_pat|glpat|xox[bap]|sk|hf)[-_][A-Za-z0-9_\-]{12,}"), "<redacted-token>"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "<redacted-aws-key>"),
]


def redact(text: str) -> str:
    for pattern, repl in SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:80] or "default"


class Session:
    def __init__(self, session_id: str, root: Path | None = None):
        self.root = root or state_dir()
        self.path = self.root / "sessions" / f"{_safe(session_id)}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def remember(self, **event) -> dict:
        event = {"ts": time.time(), **event}
        if "cmd" in event:
            event["cmd"] = redact(event["cmd"])
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def recall(self, last: int = 8) -> list:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
        return events[-last:] if last else events


class Graveyard:
    """Append-only log of the departed: deleted files, killed processes, branches."""

    def __init__(self, root: Path | None = None):
        self.path = (root or state_dir()) / "graveyard.jsonl"

    def bury(self, kind: str, name: str, cmd: str, cwd: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.time(), "kind": kind, "name": redact(name),
                                 "cmd": redact(cmd), "cwd": cwd}, ensure_ascii=False) + "\n")

    def __iter__(self) -> Iterator[dict]:
        if not self.path.exists():
            return iter(())
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
        return iter(rows)
