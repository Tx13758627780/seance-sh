---
title: "séance: I let a Gemma ghost haunt my shell (and built it an ofrenda for my deleted files)"
published: false
tags: devchallenge, hf26challenge, opensource, ai
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge: Week 4](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

> 👻 **ezequiel ›** make test again, you foolish mortal? Exit code two; a familiar echo of my own demise.

That line was written by a 4-billion-parameter model running on the CPU of a small Linux VM, about three
and a half seconds after my test suite failed for the second time in a row. No network request left
the machine to produce it. That's the whole project, really: a ghost that lives *inside* the machine,
in the most literal way I could manage.

## What I Built

**séance** is a haunted terminal. You add one line to your `.bashrc` (or `.zshrc`), and from then on
your shell is shared with **Ezequiel**, a sysadmin who died in 1999 halfway through an `fsck` and
never left the server room. After each command he whispers, in one or two sentences, what he thinks
of what you just did.

Yes, the "haunted terminal" is the first idea on the challenge's own list. I couldn't resist it, so I
tried to make it *mean* something:

* **He remembers.** Every session keeps a short memory (redacted, on disk, local). He knows this is
  your second `make test`, and he'll bring up the exit code 2 from three commands ago.
* **He reads omens.** Before the model is asked anything, plain Python works out what's actually going
  on: exit 127 means "command not found", 137 means SIGKILL, this is the 4th failure in a row, this
  command deletes things, this one is `sudo`. Gemma gets those facts; it only has to be eerie.
* **Apparitions.** Delete files and a tombstone rises. Kill a process and a calavera (sugar skull)
  grins at you. `git push --force` gets a ghost. `sudo` gets a watching eye.
* **Possession.** The more ominous things get (failure streaks, destructive commands), the more likely
  the terminal is to glitch, with Zalgo text and block noise, while the ghost "stirs".
* **`seance ofrenda`**, for Día de los Muertos. An altar of candles and marigolds for everything that
  died on your machine: files you `rm`'d, processes you `kill`ed or that got SIGKILLed, git branches you
  deleted, and the *almas en pena*, branches left untouched for months. Gemma writes a short
  remembrance for each one. It reads your shell history, the séance graveyard, the freedesktop Trash and
  the repo's reflog, and it never modifies any of them.

It's a pipx-installable Python package with zero dependencies, it works fully offline, it has no API
keys, and it's MIT-licensed.

## Demo

![séance haunting a bash session](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/REPLACE_ME/demo.gif)

The GIF above is a real recording: real bash, the real hook, and gemma3:4b answering live. The keystrokes
are typed by a small script (`scripts/demo.py`), so anyone can reproduce the recording. The only
editing is that pauses longer than 1.5 s are shortened. The latency under each whisper is what séance
measured at the time.

**Possession:** the second failing `make test` makes the terminal glitch while the ghost stirs.

![possession](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/REPLACE_ME/01-possession.png)

**Omens and apparitions:** `rm -rf` raises a tombstone, and a SIGKILLed training script gets a calavera.

![calavera](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/REPLACE_ME/04-calavera.png)

**The ofrenda:** remembrances for a deleted hotfix branch, a SIGKILLed process, two deleted files,
and an abandoned `experiment/rewrite-in-rust` branch, 117 days old.

![ofrenda](https://dev-to-uploads.s3.amazonaws.com/uploads/articles/REPLACE_ME/03-ofrenda.png)

A few lines from that recorded session, verbatim:

> 👻 **ezequiel ›** gti status. The command is a phantom, like my existence – it simply doesn't exist.
>
> 🕯️ **experiment/rewrite-in-rust** *[alma en pena · abandoned branch · 117 days ago]*
> Poor experiment/rewrite-in-rust. It wrestled with grand ambitions, a tangled promise of rust, then simply vanished into the depths of the repository.
>
> 🕯️ **~/crypt/build** *[archivo · file]*
> The build folder, a tireless worker, finally rests. May marigold petals guide its code back to Mictlan, a gentle farewell to its frantic efforts.

The typo one got me. I typed `gti` on purpose for the demo, and I still laughed.

**Code:** https://github.com/Tx13758627780/seance-sh

```bash
ollama pull gemma3:4b
pipx install git+https://github.com/Tx13758627780/seance-sh
echo 'eval "$(seance init bash)"' >> ~/.bashrc
```

## How I Built It

### The shape of it

```
bash/zsh hook ──(command, exit code, start time, cwd)──▶ seance whisper
   omens.py   deterministic facts: exit meanings, streaks, repeats, deaths, which apparition
   memory.py  last N commands this session (JSONL, secrets redacted) + a graveyard of deaths
   ghost.py   persona + memory + omens → POST /api/chat (streaming) → Ollama → Gemma 3
   effects.py "the ghost stirs" glitch while waiting → whisper streams in, word-wrapped
```

The bash hook uses a `DEBUG` trap to catch the command and its start time, plus `PROMPT_COMMAND` to
call `seance whisper` with the exit code once the command finishes. zsh uses `preexec`/`precmd`. The hook
keeps your `$?` intact, skips tab completion, and doesn't re-whisper the previous command when you just
press Enter. That last bug took me longer than any of the AI parts.

### Why Gemma, and which Gemma

I benchmarked both small Gemma 3 models through Ollama with séance's *real* prompt (persona, memory,
omens), 14 runs each, on the only hardware I had for this: **a Linux VM with 8 vCPUs (Intel Xeon),
16 GB of RAM and no GPU.** Ollama confirms it's running on CPU.

| model | cold start (load + first reply) | first word, warm (median) | full whisper, warm (median) | RAM (`ollama ps`) |
|---|---|---|---|---|
| gemma3:1b | 3.08 s | 0.90 s (0.70–1.13) | 1.78 s (1.41–2.34) | 1.2 GB |
| gemma3:4b | 6.79 s | 1.90 s (1.38–2.75) | 3.58 s (2.54–5.90) | 2.9 GB |

The 1B model is twice as fast, but in my testing its whispers were generic. They were spooky in the
abstract, but they often ignored the actual command. The 4B model reliably names the
file, the branch or the exit code, and that's what makes it feel like someone is *watching*. So
**gemma3:4b is the default**, and `SEANCE_MODEL=gemma3:1b` is one environment variable away if your
machine is slower or you want a ghost that talks faster. In the recorded demo session, the 7 whispers
had a median of **1.80 s to the first word** and **3.15 s for the full whisper**.

The benchmark script is in the repo (`scripts/bench.py`), so you can measure your own machine instead
of trusting mine.

### Hiding latency: make the waiting part of the haunting

Three seconds of nothing after every command would feel broken. So séance streams the response and, until the
first token arrives, plays a glitching `░▒▓ the ghost stirs ▓▒░` line that dissolves into the whisper.
The whisper is then typed out as it streams, word-wrapped with a hanging indent. The roughly
1.9 s wait for the first word stops feeling like lag and starts feeling like the ghost gathering itself.

For when you actually need to work, `SEANCE_RATE=0.3` keeps him quiet on calm, successful commands
(failures and destructive commands always get a whisper), and `SEANCE_HUSH=1` silences him entirely.

### Prompting a small model

Some things I learned, in roughly the order they bit me:

* **Gemma has no system role.** Gemma's chat format only has user and model turns, so I fold the persona
  into the first user turn myself instead of relying on how a server template treats a system message.
* **Small models need facts, not puzzles.** Asking "what does exit code 137 mean?" invites hallucination.
  Telling the model "Omens you sense: killed by SIGKILL (137); this is the 2nd failure in a row" gives it
  something true to be dramatic about. This is the single biggest quality improvement I made.
* **Few-shot beats adjectives.** Four example whispers in the persona did more than any amount of
  "be eerie, be specific, be concise".
* **Clean the output defensively.** The model sometimes echoes the prompt format back ("make test
  (exit 2) – …"), adds markdown, or rambles. A small `clean()` step strips that and caps the whisper at two
  sentences. An earlier version of that step also stripped the underscores out of
  `notes_from_last_halloween.txt`, which was its own small horror.
* **Variety for the ofrenda.** Each remembrance gets a different "angle" (an offering left on the
  altar, a tiny eulogy from its old friends in the codebase, marigold petals guiding it home…). Otherwise five epitaphs in a row all start
  with "Rest now".

It isn't perfect. Ezequiel brings up his own death *a lot*, and sometimes he invents history ("the
last time you checked for disks"). For a ghost, I've decided that's in character.

### Privacy, carefully

Shell history is about as private as data gets: hostnames, paths, typo'd passwords. Before anything is
stored, séance redacts `*TOKEN*/*SECRET*/*PASSWORD*` variables, `--password` flags, `Authorization:`
headers, `user:pass@` URLs, and GitHub, OpenAI, Hugging Face and AWS-style keys. There are tests for
this. And then it only ever sends that redacted text to `127.0.0.1`.

## Why Open Innovation Matters

**Because the ghost reads your shell history.** I would never pipe every command I type, with its
paths, hostnames and the odd password pasted in the wrong window, to someone else's API to get a joke
back. With an open-weight model it never has to leave the box. séance talks only to
`http://127.0.0.1:11434`. You can unplug the network cable and the haunting carries on. I measured
every number in this post on a machine with no GPU.

**Because it costs nothing to be haunted.** An always-on shell companion makes a model call after
*every* command. With a hosted API, that's a meter running all day. Locally it's 2.9 GB of RAM and a few
seconds of CPU per whisper (about 3.6 s median for gemma3:4b, 1.8 s for gemma3:1b on my 8-vCPU VM).
There's no key to leak and no bill.

**Because the model is swappable.** The 1B-vs-4B trade-off above was a decision *I* got to make,
with my own benchmarks, on my own hardware. Next year it'll be a different model, and switching is one
environment variable: `SEANCE_MODEL=<anything Ollama can run>`. No vendor decides that a fun but
pointless app is no longer worth serving.

**Because things you depend on should outlive the company that made them.** That one fits the theme a
little too well. An ofrenda is about remembering what's gone. I didn't want to build one that would join
it the day an API was deprecated. Gemma's weights are on my disk. As long as Ollama, or llama.cpp, or
whatever comes after them can load a GGUF, Ezequiel stays.

Where it was *worse* than a closed frontier model: latency and polish. A big hosted model would
whisper faster and repeat itself less. But a faster ghost that phones home with your shell history
isn't the ghost I wanted.

## Prize Categories

**Best Use of Gemma:** Gemma 3 (gemma3:4b by default, gemma3:1b optional) run locally through Ollama
is the ghost. It writes every whisper and every ofrenda remembrance, grounded by deterministic omens
and benchmarked on CPU-only hardware.

---

Thanks for reading. If you install it, run `seance ofrenda` on Nov 1 or 2. The altar notices the date. 🕯️🌼

*— xt*
