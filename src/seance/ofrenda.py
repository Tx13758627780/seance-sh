"""Día de los Muertos mode: gather the departed and remember them.

Sources (all local, all read-only):
  * the séance graveyard (things that died while the ghost was watching)
  * your shell history files (rm / kill / git branch -D you ran before séance)
  * the freedesktop Trash (~/.local/share/Trash)
  * the current git repo: branches deleted (from the reflog) and branches
    abandoned for a long time ("almas en pena", wandering souls)
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import unquote

from .memory import Graveyard, redact
from .omens import deaths_in


@dataclass
class Departed:
    kind: str          # file | process | branch | wandering-branch
    name: str
    detail: str
    when: Optional[float] = None
    source: str = ""

    @property
    def key(self):
        return (self.kind.replace("wandering-", ""), self.name)


def ago(ts: Optional[float], now: Optional[float] = None) -> str:
    if not ts:
        return "some night long ago"
    secs = max(0, (now or time.time()) - ts)
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if secs >= size:
            n = int(secs // size)
            return f"{n} {unit}{'s' if n != 1 else ''} ago"
    return "moments ago"


# ---------- sources ----------

def from_graveyard(graveyard: Graveyard) -> List[Departed]:
    out = []
    for row in graveyard:
        out.append(Departed(row["kind"], row["name"], f"put to rest by `{row.get('cmd', '?')}`",
                            row.get("ts"), "séance graveyard"))
    return out


ZSH_LINE = re.compile(r"^: (\d+):\d+;(.*)$")


def parse_history(text: str) -> List[tuple]:
    """Return (timestamp|None, command) from bash or zsh (extended) history."""
    rows, ts = [], None
    for line in text.splitlines():
        if line.startswith("#") and line[1:].isdigit():  # bash HISTTIMEFORMAT stamps
            ts = float(line[1:])
            continue
        m = ZSH_LINE.match(line)
        if m:
            rows.append((float(m.group(1)), m.group(2)))
        elif line.strip():
            rows.append((ts, line))
        ts = None
    return rows


def from_history(paths: Iterable[Path], max_lines: int = 3000) -> List[Departed]:
    out = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ts, cmd in parse_history(text)[-max_lines:]:
            if cmd.lstrip().startswith("seance"):
                continue
            for kind, name in deaths_in(cmd):
                out.append(Departed(kind, name, f"put to rest by `{redact(cmd)}`", ts, path.name))
    return out


def from_trash(trash: Path) -> List[Departed]:
    out = []
    info = trash / "info"
    if not info.is_dir():
        return out
    for f in sorted(info.glob("*.trashinfo")):
        path, when = None, None
        for line in f.read_text(errors="replace").splitlines():
            if line.startswith("Path="):
                path = unquote(line[5:])
            elif line.startswith("DeletionDate="):
                try:
                    when = time.mktime(time.strptime(line[13:], "%Y-%m-%dT%H:%M:%S"))
                except ValueError:
                    pass
        if path:
            out.append(Departed("file", path, "moved to the Trash, waiting between worlds", when, "Trash"))
    return out


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              timeout=10, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def from_git(repo: Path, stale_days: int = 30, now: Optional[float] = None) -> List[Departed]:
    now = now or time.time()
    if not _git(repo, "rev-parse", "--git-dir"):
        return []
    alive = {}
    for line in _git(repo, "for-each-ref", "--format=%(refname:short)\t%(committerdate:unix)\t%(subject)",
                     "refs/heads").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            alive[parts[0]] = (float(parts[1] or 0), parts[2] if len(parts) > 2 else "")
    current = _git(repo, "branch", "--show-current").strip()
    out, seen = [], set()
    for line in _git(repo, "reflog", "--format=%ct\t%gs").splitlines():
        ts, _, subject = line.partition("\t")
        m = re.match(r"checkout: moving from (\S+) to (\S+)", subject)
        if not m:
            continue
        for name in m.groups():
            if name in alive or name in seen or re.fullmatch(r"[0-9a-f]{7,40}", name) or name == "HEAD":
                continue
            seen.add(name)
            out.append(Departed("branch", name, "a git branch that once was checked out here and no longer exists",
                                float(ts or 0) or None, "git reflog"))
    for name, (ts, subject) in alive.items():
        if name == current:
            continue
        if now - ts > stale_days * 86400:
            out.append(Departed("wandering-branch", name,
                                f"a git branch nobody has touched for {int((now - ts) // 86400)} days; its last words were the commit '{subject}'",
                                ts, "git"))
    return out


def gather(repo: Optional[Path] = None, graveyard: Optional[Graveyard] = None,
           history_paths: Optional[Iterable[Path]] = None, trash: Optional[Path] = None,
           stale_days: int = 30) -> List[Departed]:
    home = Path.home()
    if history_paths is None:
        history_paths = [Path(os.environ.get("HISTFILE", home / ".bash_history")), home / ".zsh_history"]
    found = []
    found += from_graveyard(graveyard or Graveyard())
    found += from_history(history_paths)
    found += from_trash(trash or home / ".local/share/Trash")
    if repo is not None:
        found += from_git(repo, stale_days)
    # dedupe, keep the most informative (earliest source wins, graveyard first)
    unique, seen = [], set()
    for d in found:
        if d.key in seen:
            continue
        seen.add(d.key)
        unique.append(d)
    unique.sort(key=lambda d: -(d.when or 0))
    return unique


TEMPLATES = {
    "file": "Here lies {name}. It held its bytes faithfully until the very last rm. May its inode find rest.",
    "process": "{name} ran its loop, answered its signals, and was taken before its time. We light a candle for its PID.",
    "branch": "{name} dreamed of being merged. It sleeps now in the reflog, among the dangling commits.",
    "wandering-branch": "{name} still wanders, unmerged and unvisited. Tonight we set out marigolds so it can find its way home.",
}


def remembrance_offline(d: Departed) -> str:
    return TEMPLATES.get(d.kind, "{name} is gone, but not forgotten.").format(name=d.name)
