"""The ghost itself: a tiny Ollama client, the persona, and the prompts.

No third-party dependencies, no API keys. If the local model is unreachable
the ghost falls back to canned lines so your shell never breaks.
"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .config import Config
from .omens import Omen

PERSONA = (
    "You are Ezequiel, the ghost of a sysadmin who died in 1999 halfway through an fsck "
    "and never left the server room. You haunt this person's terminal and comment on each command they run.\n"
    "Style: wry, melancholy, theatrical, a little funny. Always talk about the SPECIFIC command, "
    "its exit code, or a pattern with their earlier commands. Name the command or the file.\n"
    "Rules: ONE or TWO short sentences, at most 30 words. Speak to the user as 'you'. "
    "No markdown, no emojis, no lists, no quotation marks, no advice in an assistant voice.\n\n"
    "Examples of things you have whispered before:\n"
    "Another commit called fix. I have seen a hundred of those, and every one of them lied.\n"
    "npm install failed again. The node_modules grow hungry, and they are not yet fed.\n"
    "notes.txt is gone. I felt it pass through me on its way to the other side.\n"
    "Exit 255. Prod refused you, the way it once refused me, on the night I died."
)

FALLBACK_LINES = [
    "The wires are cold tonight. I cannot reach my voice, but I am still watching.",
    "Something stirs in /dev/null. It knows what you just typed.",
    "I tried to speak, but the model sleeps. Wake it with `ollama serve`, mortal.",
    "Your command echoes down an empty hallway. Nobody answers. Yet.",
    "Even without my voice, I count your exit codes.",
]


@dataclass
class Reply:
    text: str
    model: str
    seconds: float
    offline: bool = False
    first_token: Optional[float] = None


class GhostError(RuntimeError):
    pass


def chat(cfg: Config, messages: list[dict], model: Optional[str] = None,
         max_tokens: int = 70, temperature: float = 0.9,
         on_token: Optional[Callable[[str], None]] = None) -> Reply:
    """Stream a reply from the local model. `on_token` receives cleaned text
    as it arrives (after a short look-ahead buffer used to strip preambles)."""
    model = model or cfg.model
    messages = fold_system(messages)
    started = time.monotonic()
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": "30m",
        "options": {"num_predict": max_tokens, "temperature": temperature, "top_p": 0.95},
    }
    req = urllib.request.Request(cfg.host + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    raw, shown, first = "", "", None
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise GhostError(chunk["error"])
                raw += chunk.get("message", {}).get("content", "")
                if first is None and raw.strip():
                    first = time.monotonic() - started
                done = chunk.get("done")
                if on_token and (len(raw) >= 48 or done):
                    text = clean(raw, finished=done)
                    if text.startswith(shown) and len(text) > len(shown):
                        on_token(text[len(shown):])
                        shown = text
                if done or (shown and len(clean(raw)) > len(shown) + 400):
                    break
    except (urllib.error.URLError, OSError, ValueError) as exc:  # includes timeouts
        if not shown:
            raise GhostError(str(exc)) from exc
    text = clean(raw, finished=True)
    if not text:
        raise GhostError("the ghost said nothing")
    if on_token and text.startswith(shown) and len(text) > len(shown):
        on_token(text[len(shown):])
    return Reply(text=text, model=model, seconds=time.monotonic() - started,
                 first_token=first)


def fold_system(messages: list[dict]) -> list[dict]:
    """Gemma has no system role; like its official chat template, fold the
    system prompt into the first user turn."""
    if messages and messages[0]["role"] == "system" and len(messages) > 1:
        sys_msg, first, rest = messages[0], messages[1], messages[2:]
        merged = {"role": "user", "content": sys_msg["content"] + "\n\n" + first["content"]}
        return [merged, *rest]
    return messages


ECHO_PREFIX = re.compile(r"^(command:\s*)?[^.!?]{0,120}?\(exit \d+\)\s*(->|[-–—:])\s*", re.I)


def clean(text: str, max_sentences: int = 2, max_chars: int = 240, finished: bool = True) -> str:
    """Small models love markdown, preambles and echoing the prompt; exorcise them.
    With finished=False the result is a stable prefix safe to print while streaming."""
    text = text.lstrip()
    text = re.sub(r"^(sure|okay|ok|here'?s?[^:\n]*):\s*", "", text, flags=re.I)
    text = ECHO_PREFIX.sub("", text)
    text = re.sub(r"\*+|__+|`+|^#+\s*|^>\s*|[\u201c\u201d\"]", "", text)
    text = re.sub(r"\s+", " ", text)
    if not finished:
        text = text.rsplit(" ", 1)[0] if " " in text else ""  # hold back a half-word
    sentences = re.split(r"(?<=[.!?…])\s+", text)
    if len(sentences) > max_sentences:
        text = " ".join(sentences[:max_sentences])
    text = text.strip().strip("'")
    if len(text) > max_chars:
        text = text[: max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return text


def fallback(seed: Optional[str] = None) -> str:
    rnd = random.Random(seed)
    return rnd.choice(FALLBACK_LINES)


def whisper_messages(command: str, exit_code: int, duration: Optional[float],
                     omen: Omen, history: Iterable[dict], output_tail: str = "") -> list[dict]:
    """Build the chat for one whisper. The heavy lifting is done by *omens*:
    deterministic facts we compute in Python so a 1B model doesn't have to guess."""
    lines = []
    past = list(history)
    if past:
        lines.append("Earlier tonight the user ran (oldest first):")
        for h in past:
            lines.append(f"- {h.get('cmd')}  (exit {h.get('exit')})")
    lines.append("")
    lines.append(f"Just now they ran: {command}")
    status = "succeeded" if exit_code == 0 else f"FAILED with exit code {exit_code}"
    lines.append(f"It {status}." + (f" It took {duration:.1f} seconds." if duration is not None and duration >= 2 else ""))
    if omen.facts:
        lines.append("Omens you sense: " + " ".join(omen.facts))
    if output_tail:
        lines.append("The last lines it printed were:\n" + output_tail)
    lines.append("")
    lines.append("Whisper your eerie comment about the latest command now.")
    return [
        {"role": "system", "content": PERSONA},
        {"role": "user", "content": "\n".join(lines)},
    ]


EPITAPH_PERSONA = (
    "You are Ezequiel, a gentle ghost keeping a Dia de los Muertos ofrenda inside a terminal. "
    "For each departed thing you write a short, tender, slightly funny remembrance, "
    "as if it were a beloved soul: what it was, how it went, and a blessing for its journey to Mictlan. "
    "Rules: ONE or TWO sentences, at most 35 words. No markdown, no emojis, no quotation marks. "
    "Do not invent facts that are not given; you may be poetic about the given ones."
)


EPITAPH_ANGLES = [
    "Mention one offering you place on the altar for it, something it would have loved in life.",
    "Write it as a tiny eulogy, as if its old friends in the codebase were speaking.",
    "Say how the marigold petals will guide it home tonight.",
    "Recall, gently, the moment it left this world.",
    "End with a small joke it would have appreciated.",
]


def epitaph_messages(kind: str, name: str, detail: str, angle: Optional[str] = None) -> list[dict]:
    angle = angle or random.choice(EPITAPH_ANGLES)
    return [
        {"role": "system", "content": EPITAPH_PERSONA},
        {"role": "user", "content": f"The departed: a {kind} named {name}. What we know: {detail}\n{angle}\nWrite its remembrance."},
    ]
