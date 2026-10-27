#!/usr/bin/env python3
"""Record the séance demo with asciinema, driving a *real* interactive bash
(with the real hook and the real local Gemma) through a pty.

    python scripts/demo.py media/demo.cast

Everything runs in a throwaway HOME so your own history stays out of it.
The only staged thing is the scenery: a small repo with one branch backdated
to July 2026 (so the ofrenda has an abandoned branch to mourn)."""
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pexpect

ROOT = Path("/tmp/seance-demo")
HOME = ROOT / "home"
CRYPT = HOME / "crypt"


def sh(*args, **kw):
    subprocess.run(args, check=True, capture_output=True, **kw)


def stage():
    shutil.rmtree(ROOT, ignore_errors=True)
    CRYPT.mkdir(parents=True)
    env = dict(os.environ, HOME=str(HOME), GIT_AUTHOR_NAME="xt", GIT_AUTHOR_EMAIL="xt@example.com",
               GIT_COMMITTER_NAME="xt", GIT_COMMITTER_EMAIL="xt@example.com")
    g = lambda *a, **k: sh("git", "-C", str(CRYPT), *a, env={**env, **k})  # noqa: E731
    g("init", "-q", "-b", "main")
    (CRYPT / "Makefile").write_text("test:\n\t@python3 -c \"import sys; print('FAILED tests/test_soul.py::test_has_soul - AssertionError: no soul found'); sys.exit(2)\"\n")
    (CRYPT / "train.py").write_text("import os, signal, time\nprint('epoch 1/400 ... loss=0.666')\ntime.sleep(1)\nos.kill(os.getpid(), signal.SIGKILL)\n")
    (CRYPT / "README.md").write_text("# crypt\nA project that will not stay dead.\n")
    g("add", "-A")
    g("commit", "-q", "-m", "first breath")
    g("checkout", "-q", "-b", "experiment/rewrite-in-rust")
    g("commit", "-q", "--allow-empty", "-m", "WIP: rewrite everything in rust (do not merge)",
      GIT_AUTHOR_DATE="2026-07-02T03:00:00", GIT_COMMITTER_DATE="2026-07-02T03:00:00")
    g("checkout", "-q", "main")
    g("checkout", "-q", "-b", "hotfix/friday-deploy")
    g("commit", "-q", "--allow-empty", "-m", "pls work")
    g("checkout", "-q", "main")
    (CRYPT / "build").mkdir()
    (CRYPT / "build" / "app.o").write_text("x")
    (CRYPT / "notes_from_last_halloween.txt").write_text("buy candles\n")
    (HOME / ".bashrc").write_text(
        'export PS1="\\[\\e[38;5;214m\\]mortal\\[\\e[0m\\]@\\[\\e[38;5;141m\\]crypt\\[\\e[0m\\] \\$ "\n'
        'export HISTFILE=~/.bash_history\ncd ~/crypt\n')


SCRIPT = [
    'eval "$(seance init bash)"',
    "ls",
    "make test",
    "make test",
    "rm -rf build/ notes_from_last_halloween.txt",
    "python3 train.py",
    "gti status",
    "git branch -D hotfix/friday-deploy",
    "seance ofrenda",
]


def main(cast: str):
    stage()
    env = dict(os.environ, HOME=str(HOME), SEANCE_HOME=str(ROOT / "state"), SEANCE_SHOW_LATENCY="1",
               TERM="xterm-256color", SHELL="/bin/bash", SEANCE_GLITCH="0.35",
               PATH=os.path.dirname(shutil.which("seance")) + ":" + os.environ["PATH"])
    for var in ("SEANCE_SESSION", "NO_COLOR", "FORCE_COLOR"):
        env.pop(var, None)
    rcmd = f"asciinema rec --overwrite -q --cols 100 --rows 34 -i 1.5 -c 'bash --rcfile {HOME}/.bashrc -i' {cast}"
    child = pexpect.spawn("bash", ["-c", rcmd], env=env, encoding="utf-8", timeout=180,
                          dimensions=(34, 100), cwd=str(HOME))
    child.logfile_read = sys.stdout
    prompt = r"crypt.*\$ "
    child.expect(prompt)
    time.sleep(1.0)
    for line in SCRIPT:
        for ch in line:
            child.send(ch)
            time.sleep(random.uniform(0.03, 0.09))
        time.sleep(0.4)
        child.send("\r")
        child.expect(prompt)
        time.sleep(1.8)
    child.send("exit\r")
    child.expect(pexpect.EOF)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "media/demo.cast"))
