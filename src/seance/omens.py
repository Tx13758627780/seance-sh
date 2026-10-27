"""Omens: deterministic readings of a command, computed *before* the model
speaks. They ground a tiny model in facts (what exit 137 means, that this is
the third failure in a row) and decide how hard the terminal gets possessed."""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Iterable, Optional

EXIT_MEANINGS = {
    1: "Exit 1 is a generic failure.",
    2: "Exit 2 usually means it was used wrongly.",
    126: "Exit 126 means the file exists but is not executable.",
    127: "Exit 127 means the command does not exist at all, like a name with no body.",
    130: "Exit 130 means the user killed it with Ctrl-C.",
    137: "Exit 137 means it was murdered with SIGKILL, perhaps by the OOM killer.",
    139: "Exit 139 means a segmentation fault, it touched memory it should not have.",
    143: "Exit 143 means it was terminated with SIGTERM.",
}

DESTRUCTIVE = [
    (re.compile(r"\brm\s+(-\w*[rf]\w*\s+)+"), "It forcefully deletes files, maybe forever."),
    (re.compile(r"\brm\b"), "It deletes files."),
    (re.compile(r"\bgit\s+push\b.*(--force|-f\b)"), "It force-pushes, rewriting shared history."),
    (re.compile(r"\bgit\s+reset\s+--hard"), "It throws away uncommitted work."),
    (re.compile(r"\bgit\s+branch\s+-D\b"), "It deletes a git branch."),
    (re.compile(r"\bgit\s+clean\s+-\w*f"), "It purges untracked files."),
    (re.compile(r"\b(kill|pkill|killall)\b"), "It kills a process."),
    (re.compile(r"\bdd\s+if="), "It writes raw bytes to a disk."),
    (re.compile(r"\bmkfs\b"), "It formats a filesystem."),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "It makes files writable by anyone."),
    (re.compile(r"\bdocker\s+(rm|rmi|system\s+prune)\b"), "It destroys containers or images."),
]

ART_FOR = {"kill": "calavera", "rm": "tombstone", "git": "ghost", "fail": "ghost", "sudo": "eye"}


@dataclass
class Omen:
    facts: list = field(default_factory=list)
    severity: int = 0            # 0 calm .. 3 full possession
    art: Optional[str] = None    # which ASCII art to manifest
    deaths: list = field(default_factory=list)  # (kind, name) things that died


def _words(command: str) -> list:
    try:
        return shlex.split(command, comments=True)
    except ValueError:
        return command.split()


def deaths_in(command: str, exit_code: int = 0, cwd: str = "") -> list:
    """Things a command put to rest: files, processes, branches."""
    out = []
    for segment in re.split(r"\s*(?:&&|\|\||;|\|)\s*", command):
        w = _words(segment)
        while w and (w[0] in ("sudo", "command", "nohup") or "=" in w[0]):
            w = w[1:]
        if not w:
            continue
        head = os.path.basename(w[0])
        args = [a for a in w[1:] if not a.startswith("-")]
        if head in ("rm", "unlink", "shred", "rmdir"):
            out += [("file", os.path.normpath(os.path.join(cwd, a)) if cwd else a) for a in args]
        elif head == "git" and len(w) > 2 and w[1] == "rm":
            out += [("file", a) for a in args[1:]]
        elif head == "git" and len(w) > 2 and w[1] == "branch" and ("-D" in w or "-d" in w or "--delete" in w):
            out += [("branch", a) for a in args[1:]]
        elif head in ("kill", "pkill", "killall"):
            out += [("process", a) for a in args if not re.fullmatch(r"-?\d{1,2}|-[A-Z]+", a)]
    if exit_code in (137, 143, 130):
        name = os.path.basename(_words(command)[0]) if _words(command) else command
        out.append(("process", f"{name} (exit {exit_code})"))
    return out


def read(command: str, exit_code: int, duration: Optional[float] = None,
         history: Iterable[dict] = ()) -> Omen:
    omen = Omen()
    past = list(history)
    cmd = command.strip()

    for pattern, fact in DESTRUCTIVE:
        if pattern.search(cmd):
            omen.facts.append(fact)
            omen.severity = max(omen.severity, 2)
            break

    if re.match(r"^\s*sudo\b", cmd):
        omen.facts.append("They invoked root powers with sudo.")
        omen.severity = max(omen.severity, 1)
        omen.art = omen.art or ART_FOR["sudo"]

    if exit_code != 0:
        omen.facts.append(EXIT_MEANINGS.get(exit_code, f"Exit {exit_code} means something went wrong."))
        omen.severity = max(omen.severity, 1)
        streak = 1
        for h in reversed(past):
            if h.get("exit", 0) != 0:
                streak += 1
            else:
                break
        if streak >= 2:
            omen.facts.append(f"That is {streak} failures in a row.")
            omen.severity = max(omen.severity, 2 if streak < 4 else 3)

    same = [h for h in past if h.get("cmd") == cmd]
    if same:
        omen.facts.append(f"They already ran this exact command {len(same)} time(s) tonight.")
        if exit_code != 0 and any(h.get("exit") != 0 for h in same):
            omen.facts.append("It failed before too, and they tried again anyway.")
            omen.severity = max(omen.severity, 2)

    if duration is not None and duration > 10:
        omen.facts.append(f"It ran for a long {duration:.0f} seconds.")

    deaths = deaths_in(cmd, exit_code)
    omen.deaths = deaths
    if deaths:
        kinds = {k for k, _ in deaths}
        if "process" in kinds:
            omen.art = "calavera"
        elif "file" in kinds:
            omen.art = "tombstone"
        omen.severity = max(omen.severity, 2)
    elif re.search(r"\bgit\s+(push\s+.*(--force|-f\b)|reset\s+--hard)", cmd):
        omen.art = "ghost"
    if omen.severity >= 3 and not omen.art:
        omen.art = "ghost"
    return omen
