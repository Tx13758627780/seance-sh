#!/usr/bin/env python3
"""Turn moments of an asciinema cast into PNG screenshots using agg + ffmpeg.

    python scripts/screenshots.py media/demo.cast media/ 380:possession 684:whispers 1912:ofrenda

Each argument is EVENT_INDEX:name; the screenshot shows the terminal exactly as
it looked right after that output event."""
import json
import os
import subprocess
import sys
import tempfile

FONTS = "JetBrains Mono,Noto Color Emoji,Noto Sans Symbols,DejaVu Sans Mono"


def main(cast, outdir, *shots):
    lines = open(cast, encoding="utf-8").read().splitlines()
    header, events = lines[0], lines[1:]
    for shot in shots:
        idx, name = shot.split(":")
        with tempfile.TemporaryDirectory() as tmp:
            part = os.path.join(tmp, "part.cast")
            with open(part, "w", encoding="utf-8") as fh:
                fh.write(header + "\n" + "\n".join(events[: int(idx) + 1]) + "\n")
            gif = os.path.join(tmp, "part.gif")
            subprocess.run(["agg", "--font-family", FONTS, "--font-size", "16", "--theme", "monokai",
                            "--idle-time-limit", "0.2", "--last-frame-duration", "1", part, gif],
                           check=True, capture_output=True)
            png = os.path.join(outdir, f"{name}.png")
            # keep overwriting one PNG with every frame: the survivor is the last frame
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", gif, "-update", "1", png], check=True)
            print("wrote", png, json.loads(events[int(idx)])[0])


if __name__ == "__main__":
    main(*sys.argv[1:])
