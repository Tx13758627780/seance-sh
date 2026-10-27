#!/usr/bin/env python3
"""Measure the ghost's latency on this machine with the real séance prompts.

    python scripts/bench.py gemma3:1b gemma3:4b --runs 10
"""
import argparse
import statistics
import sys
import time
import urllib.request
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from seance import ghost, omens  # noqa: E402
from seance.config import Config  # noqa: E402

COMMANDS = [("ls -la", 0), ("make test", 2), ("rm -rf build/", 0), ("python train.py", 137),
            ("gti status", 127), ("git push --force origin main", 0), ("sudo systemctl restart nginx", 0)]


def unload(cfg, model):
    req = urllib.request.Request(cfg.host + "/api/generate", json.dumps({"model": model, "keep_alive": 0}).encode(),
                                 {"Content-Type": "application/json"})
    urllib.request.urlopen(req).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+")
    ap.add_argument("--runs", type=int, default=7)
    a = ap.parse_args()
    cfg = Config()
    cfg.timeout = 120
    for model in a.models:
        unload(cfg, model)
        t = time.monotonic()
        ghost.chat(cfg, [{"role": "user", "content": "Say boo."}], model=model, max_tokens=5)
        cold = time.monotonic() - t
        ttft, total, words = [], [], []
        history = []
        for i in range(a.runs):
            cmd, code = COMMANDS[i % len(COMMANDS)]
            omen = omens.read(cmd, code, None, history)
            r = ghost.chat(cfg, ghost.whisper_messages(cmd, code, None, omen, history), model=model)
            history.append({"cmd": cmd, "exit": code})
            ttft.append(r.first_token)
            total.append(r.seconds)
            words.append(len(r.text.split()))
            print(f"  {model} {cmd!r:38} first={r.first_token:.2f}s total={r.seconds:.2f}s | {r.text}")
        print(f"{model}: cold load+first reply {cold:.2f}s | warm first word median {statistics.median(ttft):.2f}s "
              f"(min {min(ttft):.2f}, max {max(ttft):.2f}) | full whisper median {statistics.median(total):.2f}s "
              f"(min {min(total):.2f}, max {max(total):.2f}) | ~{statistics.mean(words):.0f} words\n")
        unload(cfg, model)


if __name__ == "__main__":
    main()
