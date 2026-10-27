"""Possession effects: colour, flicker, typed whispers and ASCII apparitions.
Everything degrades to plain text when stdout is not a TTY or NO_COLOR is set."""

from __future__ import annotations

import os
import random
import sys
import time

ESC = "\033["
RESET = ESC + "0m"
PALETTE = {
    "violet": ESC + "38;5;141m",
    "dim": ESC + "2m",
    "italic": ESC + "3m",
    "red": ESC + "38;5;196m",
    "blood": ESC + "38;5;124m",
    "green": ESC + "38;5;48m",
    "marigold": ESC + "38;5;214m",
    "pink": ESC + "38;5;205m",
    "bone": ESC + "38;5;230m",
    "grey": ESC + "38;5;244m",
    "bold": ESC + "1m",
}
GLITCH_CHARS = "▓▒░█▚▞▙▟╳ⱷ҉̷̸Ϟ#@%&$"
ZALGO = [chr(c) for c in range(0x0300, 0x036F)]

ART = {
    "ghost": r"""
      .-.
     (o o)   boo.
     | O \
      \   \
       `~~~'
""",
    "tombstone": r"""
      _____
     /     \
    | R.I.P |
    |  ~~~  |
    |_______|
   ~~~~~~~~~~~
""",
    "calavera": r"""
     .-''''-.
    /  _  _  \
   |  (o)(o)  |
   |    /\    |
    \ \/\/\/ /
     '-.__.-'
""",
    "eye": r"""
     .-~~~-.
    (  (@)  )   i see you, root.
     '-~~~-'
""",
}

OFRENDA_HEADER = r"""
                 🕯️      🕯️      🕯️
            ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿
               .-''''-.     .-''''-.
              /  ❀  ❀ \   /  ❀  ❀ \
             |   .--.  | |   .--.  |
              \ '----' /   \ '----' /
               '-.__.-'     '-.__.-'
          ════════════════════════════════
            O F R E N D A   D I G I T A L
          ════════════════════════════════
"""


def enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("SEANCE_FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def paint(text: str, *styles: str, stream=None) -> str:
    if not enabled(stream):
        return text
    return "".join(PALETTE[s] for s in styles) + text + RESET


def corrupt(text: str, amount: float, rnd: random.Random) -> str:
    out = []
    for ch in text:
        roll = rnd.random()
        if ch != " " and roll < amount:
            out.append(rnd.choice(GLITCH_CHARS))
        elif ch != " " and roll < amount * 1.6:
            out.append(ch + rnd.choice(ZALGO))
        else:
            out.append(ch)
    return "".join(out)


def possess(text: str, intensity: int = 1, stream=None, rnd: random.Random | None = None) -> None:
    """Flicker a line between corrupted and true forms, then let it settle."""
    stream = stream or sys.stdout
    rnd = rnd or random.Random()
    if not enabled(stream):
        return
    frames = 3 + 2 * intensity
    for i in range(frames):
        amount = max(0.05, 0.55 - i * (0.5 / frames)) * (0.6 + 0.3 * intensity)
        color = rnd.choice(["red", "blood", "violet", "green"])
        line = corrupt(text, amount, rnd)
        stream.write("\r" + ESC + "2K" + PALETTE[color] + line + RESET)
        stream.flush()
        time.sleep(rnd.uniform(0.03, 0.09))
    stream.write("\r" + ESC + "2K")
    stream.flush()


def typewrite(text: str, delay: float, stream=None, styles=("violet", "italic")) -> None:
    """Print text word-wrapped with a hanging indent equal to its leading spaces."""
    import shutil

    stream = stream or sys.stdout
    on = enabled(stream)
    indent = len(text) - len(text.lstrip(" "))
    if on:
        stream.write("".join(PALETTE[s] for s in styles))
    stream.write(" " * indent)
    w = Wrapper(stream, shutil.get_terminal_size((100, 24)).columns - 1, indent, indent, delay if on else 0)
    w.feed(text.lstrip(" "))
    w.close()
    stream.write((RESET if on else "") + "\n")
    stream.flush()


def manifest(name: str, stream=None, color: str = "grey") -> None:
    stream = stream or sys.stdout
    art = ART.get(name)
    if art:
        stream.write(paint(art.strip("\n") + "\n", color, stream=stream))
        stream.flush()


def stir(text: str, intensity: int, ready, stream=None, rnd: random.Random | None = None,
         possessed: bool = True) -> None:
    """Animate a short placeholder line until `ready()` is true. This is the
    ghost arriving: it also hides the model's time-to-first-token."""
    stream = stream or sys.stdout
    rnd = rnd or random.Random()
    if not enabled(stream):
        while not ready():
            time.sleep(0.02)
        return
    i = 0
    while not ready():
        if possessed:
            amount = rnd.uniform(0.15, 0.5) * (0.6 + 0.3 * intensity)
            color = rnd.choice(["red", "blood", "violet", "green"])
            line = PALETTE[color] + corrupt(text, amount, rnd) + RESET
        else:
            line = PALETTE["grey"] + PALETTE["dim"] + text + "." * (i % 4) + RESET
        stream.write("\r" + ESC + "2K" + line)
        stream.flush()
        time.sleep(rnd.uniform(0.04, 0.09) if possessed else 0.25)
        i += 1
    stream.write("\r" + ESC + "2K")
    stream.flush()


class Wrapper:
    """Word-wraps streamed text with a hanging indent, so whispers never break mid-word."""

    def __init__(self, stream, width: int, indent: int, col: int, delay: float = 0.0):
        self.stream, self.width, self.indent, self.col, self.delay = stream, max(20, width), indent, col, delay
        self.word = ""

    def _emit(self, text: str) -> None:
        if self.delay > 0:
            for ch in text:
                self.stream.write(ch)
                self.stream.flush()
                time.sleep(self.delay * (4 if ch in ".,…" else 1))
        else:
            self.stream.write(text)
            self.stream.flush()

    def _flush_word(self) -> None:
        if not self.word:
            return
        if self.col + len(self.word) > self.width and self.col > self.indent:
            self.stream.write("\n" + " " * self.indent)
            self.col = self.indent
        self._emit(self.word)
        self.col += len(self.word)
        self.word = ""

    def feed(self, text: str) -> None:
        for ch in text:
            if ch == " ":
                self._flush_word()
                if self.col < self.width:
                    self._emit(" ")
                    self.col += 1
            else:
                self.word += ch

    def close(self) -> None:
        self._flush_word()
