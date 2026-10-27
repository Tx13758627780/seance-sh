"""Talks to a real local Ollama. Skipped automatically when none is running."""
import json
import urllib.request

import pytest

from seance import ghost, omens
from seance.config import Config

cfg = Config()


def _has_model():
    try:
        with urllib.request.urlopen(cfg.host + "/api/tags", timeout=2) as r:
            return any(m["name"].startswith(cfg.model) for m in json.load(r)["models"])
    except OSError:
        return False


@pytest.mark.skipif(not _has_model(), reason="no local Ollama/Gemma")
def test_gemma_whispers_something_short():
    omen = omens.read("git push --force", 0, None, [])
    chunks = []
    reply = ghost.chat(cfg, ghost.whisper_messages("git push --force", 0, None, omen, []), on_token=chunks.append)
    assert reply.text and len(reply.text) <= 241
    assert "".join(chunks) == reply.text
    assert reply.first_token is not None and reply.first_token <= reply.seconds
