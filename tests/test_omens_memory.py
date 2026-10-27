from seance import omens
from seance.ghost import clean, fold_system, whisper_messages
from seance.memory import Session, redact


def test_exit_codes_become_omens():
    omen = omens.read("python train.py", 137, None, [])
    assert any("SIGKILL" in f for f in omen.facts)
    assert omen.art == "calavera"
    assert ("process", "python train.py (SIGKILL)") in omen.deaths


def test_failure_streak_escalates_possession():
    history = [{"cmd": "make test", "exit": 2}, {"cmd": "make test", "exit": 2}, {"cmd": "make", "exit": 2}]
    omen = omens.read("make test", 2, None, history)
    assert "That is 4 failures in a row." in omen.facts
    assert omen.severity == 3
    assert any("failed before too" in f for f in omen.facts)


def test_deaths_are_parsed_from_compound_commands():
    deaths = omens.deaths_in("cd x && sudo rm -rf build/ notes.txt; git branch -D old-idea | cat; pkill -9 node")
    assert ("file", "build/") in deaths
    assert ("file", "notes.txt") in deaths
    assert ("branch", "old-idea") in deaths
    assert ("process", "node") in deaths


def test_redaction_keeps_secrets_out_of_memory(tmp_path):
    s = Session("t", root=tmp_path)
    s.remember(cmd="GITHUB_TOKEN=ghp_abcdefghijklmnop1234 curl -H 'Authorization: Bearer abc.def' https://u:pw@x.io")
    text = s.path.read_text()
    assert "ghp_" not in text and "abc.def" not in text and ":pw@" not in text
    assert redact("mysql --password=hunter2 db") == "mysql --password=<redacted> db"


def test_session_memory_roundtrip(tmp_path):
    s = Session("x/../y", root=tmp_path)
    for i in range(12):
        s.remember(cmd=f"echo {i}", exit=0)
    recalled = s.recall(5)
    assert [r["cmd"] for r in recalled] == [f"echo {i}" for i in range(7, 12)]
    assert s.path.parent == tmp_path / "sessions"


def test_clean_exorcises_markdown_and_echoes():
    assert clean("**Boo.** You ran `ls`. Again. And again.") == "Boo. You ran ls."
    assert clean("make test (exit 2) – The tests hate you.") == "The tests hate you."
    assert clean("old_notes.txt is gone.") == "old_notes.txt is gone."


def test_prompt_contains_memory_and_omens():
    omen = omens.read("make test", 2, None, [{"cmd": "make test", "exit": 2}])
    msgs = fold_system(whisper_messages("make test", 2, 3.0, omen, [{"cmd": "make test", "exit": 2}]))
    assert len(msgs) == 1 and msgs[0]["role"] == "user"  # Gemma has no system role
    body = msgs[0]["content"]
    assert "Ezequiel" in body and "Earlier tonight" in body and "exit code 2" in body
    assert "It took 3.0 seconds" in body
