"""séance — command line entry point."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import queue
import random
import subprocess
import sys
import threading
import time
import urllib.request
from collections import deque
from pathlib import Path

from . import __version__, effects, ghost, omens
from .config import Config, state_dir
from .hooks import HOOKS
from .memory import Graveyard, Session, redact
from .ofrenda import Departed, ago, gather, remembrance_offline

GHOST_TAG = "👻 ezequiel ›"


# ---------------------------------------------------------------- whisper

def speak(cfg: Config, messages: list, stream, styles, possessed: bool, intensity: int,
          rnd: random.Random, prefix: str = GHOST_TAG + " ", model: str | None = None,
          max_tokens: int = 70, temperature: float = 0.9, fallback_seed: str = "",
          fallback_text: str | None = None, stir_text: str | None = None) -> "ghost.Reply":
    """Ask the ghost in a background thread; animate its arrival; stream its words."""
    q: queue.Queue = queue.Queue()
    result: dict = {}

    def worker():
        try:
            result["reply"] = ghost.chat(cfg, messages, model=model, max_tokens=max_tokens,
                                         temperature=temperature, on_token=q.put)
        except ghost.GhostError as exc:
            result["error"] = exc
        finally:
            q.put(None)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    effects.stir(prefix + (stir_text or ("░▒▓ the ghost stirs ▓▒░" if possessed else "the ghost stirs")), intensity,
                 lambda: not q.empty(), stream, rnd, possessed)
    on = effects.enabled(stream)
    start = "".join(effects.PALETTE[s] for s in styles) if on else ""
    first = True
    while True:
        chunk = q.get()
        if chunk is None:
            break
        if first:
            stream.write(start + prefix)
            first = False
        if on and cfg.type_delay > 0:
            for ch in chunk:
                stream.write(ch)
                stream.flush()
                time.sleep(cfg.type_delay)
        else:
            stream.write(chunk)
        stream.flush()
    t.join()
    if "reply" in result:
        reply = result["reply"]
    else:
        reply = ghost.Reply(fallback_text or ghost.fallback(fallback_seed), model or cfg.model, 0.0, offline=True)
        stream.write(start + prefix + reply.text)
    stream.write((effects.RESET if on else "") + "\n")
    stream.flush()
    return reply


def haunt(cfg: Config, command: str, exit_code: int, duration: float | None, cwd: str,
          output_tail: str = "", stream=None, rnd: random.Random | None = None) -> dict:
    stream = stream or sys.stdout
    rnd = rnd or random.Random()
    session = Session(cfg.session)
    history = session.recall(cfg.memory)
    omen = omens.read(command, exit_code, duration, history)

    graveyard = Graveyard()
    for kind, name in omens.deaths_in(command, exit_code, cwd):
        graveyard.bury(kind, name, command, cwd)

    messages = ghost.whisper_messages(redact(command), exit_code, duration, omen,
                                      history, redact(output_tail))

    if omen.art:
        effects.manifest(omen.art, stream, "blood" if omen.severity >= 2 else "grey")
    possessed = omen.severity >= 3 or rnd.random() < cfg.glitch * (1 + omen.severity)
    styles = ("red", "italic") if omen.severity >= 2 else ("violet", "italic")
    reply = speak(cfg, messages, stream, styles, possessed, max(1, omen.severity), rnd,
                  fallback_seed=command)
    if os.environ.get("SEANCE_SHOW_LATENCY"):
        note = ("offline: the model did not answer" if reply.offline else
                f"{reply.model} · first word {reply.first_token or 0:.2f}s · full {reply.seconds:.2f}s · local")
        stream.write(effects.paint(f"   ({note})", "grey", "dim", stream=stream) + "\n")
    return session.remember(cmd=command, exit=exit_code, duration=duration, cwd=cwd,
                            whisper=reply.text, model=reply.model,
                            latency=round(reply.seconds, 3),
                            first_token=round(reply.first_token or 0, 3), offline=reply.offline,
                            severity=omen.severity, possessed=possessed)


def cmd_whisper(args, cfg: Config) -> int:
    command = " ".join(args.command).strip()
    if not command or command.split()[0] in ("seance", "clear", "reset", "exit"):
        return 0
    duration = None
    if args.started:
        try:
            duration = max(0.0, time.time() - float(args.started))
        except ValueError:
            pass
    cwd = args.cwd or os.getcwd()
    omen = omens.read(command, args.exit, duration, [])
    if args.exit == 0 and omen.severity == 0 and random.random() >= cfg.rate:
        # the ghost stays silent this time, but it still remembers
        Session(cfg.session).remember(cmd=command, exit=args.exit, duration=duration, cwd=cwd, whisper=None)
        return 0
    haunt(cfg, command, args.exit, duration, cwd)
    return 0


def cmd_run(args, cfg: Config) -> int:
    argv = args.command
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("usage: seance run -- <command> [args...]", file=sys.stderr)
        return 2
    tail: deque = deque(maxlen=12)
    started = time.time()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1)
    except FileNotFoundError:
        code = 127
        print(f"seance: {argv[0]}: command not found", file=sys.stderr)
    else:
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                tail.append(line.rstrip("\n")[:200])
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            code = 130
        if code < 0:  # killed by signal N -> shell convention 128+N
            code = 128 - code
    haunt(cfg, " ".join(argv), code, time.time() - started, os.getcwd(), "\n".join(tail))
    return code


# ---------------------------------------------------------------- ofrenda

KIND_LABEL = {
    "file": "archivo · file",
    "process": "proceso · process",
    "branch": "rama · git branch",
    "wandering-branch": "alma en pena · abandoned branch",
}


def cmd_ofrenda(args, cfg: Config) -> int:
    repo = Path(args.repo or os.getcwd())
    departed = gather(repo=repo, stale_days=args.days)[: args.limit]
    out = sys.stdout
    print(effects.paint(effects.OFRENDA_HEADER, "marigold", stream=out))
    today = dt.date.today()
    if (today.month, today.day) in ((11, 1), (11, 2)):
        print(effects.paint("   Tonight the veil is thinnest. They can hear you.\n", "pink", "bold", stream=out))
    if not departed:
        print(effects.paint("   No one has died here yet. Give it time.", "grey", stream=out))
        return 0
    md = [f"# Ofrenda digital — {today.isoformat()}", ""]
    home = str(Path.home())
    angles = random.sample(ghost.EPITAPH_ANGLES, len(ghost.EPITAPH_ANGLES))
    for i, d in enumerate(departed):
        if d.name.startswith(home + os.sep):
            d.name = "~" + d.name[len(home):]
        if args.no_ai:
            text, note = remembrance_offline(d), "offline template"
        else:
            text = None
        label = KIND_LABEL.get(d.kind, d.kind)
        print(effects.paint("  🕯️  ", "marigold", stream=out) + effects.paint(d.name, "bone", "bold", stream=out)
              + effects.paint(f"   [{label} · {ago(d.when)}]", "grey", stream=out))
        if text is None:
            r = speak(cfg, ghost.epitaph_messages(d.kind.replace("-", " "), d.name, d.detail,
                                                       angles[i % len(angles)]), out,
                      ("pink", "italic"), False, 1, random.Random(), prefix="      ",
                      model=cfg.ofrenda_model, max_tokens=90, temperature=0.8,
                      fallback_text=remembrance_offline(d), stir_text="lighting a candle")
            text, note = r.text, ("offline template" if r.offline else f"{r.model} · {r.seconds:.1f}s")
        else:
            effects.typewrite("      " + text, cfg.type_delay, out, ("pink", "italic"))
        if os.environ.get("SEANCE_SHOW_LATENCY"):
            print(effects.paint(f"      ({note})", "grey", "dim", stream=out))
        print(effects.paint("      ✿ ✿ ✿", "marigold", stream=out))
        md += [f"## 🕯️ {d.name}", f"*{label} — {ago(d.when)} — source: {d.source}*", "", text, ""]
    print(effects.paint("\n   Que descansen en paz. Their bytes return to the void.\n", "grey", "italic", stream=out))
    if args.out:
        Path(args.out).write_text("\n".join(md), encoding="utf-8")
        print(effects.paint(f"   remembrance written to {args.out}", "grey", stream=out))
    return 0


# ---------------------------------------------------------------- misc

def cmd_init(args, cfg: Config) -> int:
    shell = args.shell or os.path.basename(os.environ.get("SHELL", "bash"))
    if shell not in HOOKS:
        print(f"seance: unsupported shell {shell!r} (bash and zsh are haunted so far)", file=sys.stderr)
        return 2
    print(HOOKS[shell])
    return 0


def cmd_doctor(args, cfg: Config) -> int:
    print(f"séance {__version__}  host={cfg.host}  whisper model={cfg.model}  ofrenda model={cfg.ofrenda_model}")
    try:
        with urllib.request.urlopen(cfg.host + "/api/tags", timeout=5) as resp:
            names = [m["name"] for m in json.load(resp).get("models", [])]
        print("ollama reachable; local models:", ", ".join(names) or "(none)")
    except OSError as exc:
        print(f"ollama NOT reachable ({exc}). Start it with `ollama serve`; the ghost will use canned lines meanwhile.")
        return 1
    for model in dict.fromkeys([cfg.model, cfg.ofrenda_model]):
        if model not in names and f"{model}:latest" not in names:
            print(f"  missing {model}: run `ollama pull {model}`")
            continue
        try:
            r = ghost.chat(cfg, ghost.whisper_messages("echo hello", 0, None, omens.Omen(), []), model=model)
            print(f"  {model}: {r.seconds:.2f}s  → {r.text}")
        except ghost.GhostError as exc:
            print(f"  {model}: error {exc}")
    print("state dir:", state_dir())
    return 0


def cmd_forget(args, cfg: Config) -> int:
    session = Session(cfg.session)
    if session.path.exists():
        session.path.unlink()
    if args.all:
        g = Graveyard()
        if g.path.exists():
            g.path.unlink()
    print("The ghost forgets." + (" Even the graveyard is gone." if args.all else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="seance", description="A haunted terminal: a local Gemma ghost whispers about your commands.")
    p.add_argument("--version", action="version", version=f"séance {__version__}")
    p.add_argument("--model", help="Ollama model for whispers (default gemma3:4b, env SEANCE_MODEL)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="print the shell hook: eval \"$(seance init bash)\"")
    s.add_argument("shell", nargs="?", choices=sorted(HOOKS))
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("whisper", help="(used by the hook) comment on a finished command")
    s.add_argument("--exit", type=int, default=0)
    s.add_argument("--started", default="")
    s.add_argument("--cwd", default="")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_whisper)

    s = sub.add_parser("run", help="run a command, capture its output, and let the ghost read it")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("ofrenda", help="Día de los Muertos: remember deleted files, killed processes, lost branches")
    s.add_argument("--repo", help="git repo to search for lost branches (default: cwd)")
    s.add_argument("--limit", type=int, default=7)
    s.add_argument("--days", type=int, default=30, help="a branch untouched this long is an alma en pena")
    s.add_argument("--no-ai", action="store_true", help="use offline templates instead of Gemma")
    s.add_argument("--ofrenda-model", help="model for remembrances (default gemma3:4b)")
    s.add_argument("--out", help="also write the remembrances to a Markdown file")
    s.set_defaults(func=cmd_ofrenda)

    s = sub.add_parser("doctor", help="check that Ollama and the Gemma models are ready")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("forget", help="erase this session's haunting memory")
    s.add_argument("--all", action="store_true", help="also erase the graveyard")
    s.set_defaults(func=cmd_forget)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config()
    if args.model:
        cfg.model = args.model
    if getattr(args, "ofrenda_model", None):
        cfg.ofrenda_model = args.ofrenda_model
    if args.cmd == "whisper" and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    try:
        return args.func(args, cfg)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0
