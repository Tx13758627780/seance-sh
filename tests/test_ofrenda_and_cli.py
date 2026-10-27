import io
import subprocess
import time

from seance import cli, ghost
from seance.config import Config
from seance.memory import Graveyard
from seance.ofrenda import from_git, from_trash, gather, parse_history


def git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def test_git_branches_deleted_and_abandoned(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "a@b.c")
    git(repo, "config", "user.name", "t")
    git(repo, "commit", "-q", "--allow-empty", "-m", "root")
    git(repo, "checkout", "-q", "-b", "doomed")
    git(repo, "checkout", "-q", "main")
    git(repo, "branch", "-q", "-D", "doomed")
    git(repo, "branch", "-q", "lonely")
    found = {d.name: d.kind for d in from_git(repo, stale_days=30, now=time.time() + 90 * 86400)}
    assert found["doomed"] == "branch"
    assert found["lonely"] == "wandering-branch"
    assert "main" not in found


def test_history_parsing_bash_and_zsh():
    rows = parse_history("#1700000000\nrm a.txt\n: 1700000100:0;kill 42\nls\n")
    assert rows == [(1700000000.0, "rm a.txt"), (1700000100.0, "kill 42"), (None, "ls")]


def test_trash_and_graveyard_are_gathered(tmp_path):
    info = tmp_path / "Trash" / "info"
    info.mkdir(parents=True)
    (info / "a.trashinfo").write_text("[Trash Info]\nPath=/home/me/my%20cat.jpg\nDeletionDate=2026-10-30T23:59:00\n")
    assert from_trash(tmp_path / "Trash")[0].name == "/home/me/my cat.jpg"
    g = Graveyard(root=tmp_path)
    g.bury("file", "/w/old.log", "rm old.log", "/w")
    hist = tmp_path / "hist"
    hist.write_text("rm /w/old.log\ngit branch -D spike\n")
    departed = gather(repo=None, graveyard=g, history_paths=[hist], trash=tmp_path / "Trash")
    names = [d.name for d in departed]
    assert names.count("/w/old.log") == 1 and "spike" in names and "/home/me/my cat.jpg" in names


def test_ghost_falls_back_when_ollama_is_gone(tmp_path, monkeypatch):
    monkeypatch.setenv("SEANCE_HOME", str(tmp_path))
    monkeypatch.setenv("SEANCE_TYPE_DELAY", "0")
    cfg = Config(host="http://127.0.0.1:9", timeout=1)
    out = io.StringIO()
    event = cli.haunt(cfg, "rm -rf build", 0, 0.1, str(tmp_path), stream=out)
    assert event["offline"] is True
    assert event["whisper"] in ghost.FALLBACK_LINES
    assert "R.I.P" in out.getvalue()  # the tombstone still manifests
    assert (tmp_path / "graveyard.jsonl").exists()


def test_init_prints_hooks(capsys):
    assert cli.main(["init", "bash"]) == 0
    assert "trap '__seance_preexec' DEBUG" in capsys.readouterr().out
    assert cli.main(["init", "zsh"]) == 0
    assert "add-zsh-hook precmd" in capsys.readouterr().out
