# Benchmarks

Measured on 2026-10-27 with `python scripts/bench.py gemma3:1b gemma3:4b --runs 14`
(raw output: [`bench-2026-10-27.txt`](bench-2026-10-27.txt)).

Machine: Linux VM, 8 vCPU Intel Xeon, 16 GB RAM, **no GPU** (Ollama reports `inference compute: cpu`).
Ollama 0.40.11, official `gemma3:1b` and `gemma3:4b` (Q4_K_M) builds. Each whisper uses séance's real
prompt (persona + up to 14 earlier commands of memory + omens), streamed, max 70 tokens.

| model | cold load + first reply | warm: first word (median, min–max) | warm: full whisper (median, min–max) |
|---|---|---|---|
| gemma3:1b | 3.08 s | 0.90 s (0.70–1.13) | 1.78 s (1.41–2.34) |
| gemma3:4b | 6.79 s | 1.90 s (1.38–2.75) | 3.58 s (2.54–5.90) |

The recorded demo session (`media/demo.cast`, gemma3:4b, warm) logged 7 whispers with a median of
**1.80 s to the first word** (1.44–2.31 s) and **3.15 s for the full whisper** (2.63–4.27 s).
Ofrenda remembrances with gemma3:4b took 2.6–4.5 s each.

Memory as reported by `ollama ps` while loaded: gemma3:4b 2.9 GB, gemma3:1b 1.2 GB.
