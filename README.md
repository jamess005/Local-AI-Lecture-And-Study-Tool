# Local AI Lecture & Study Tool

An offline desktop application that uses lecture transcriptions, generates structured notes, and lets you study them with AI-generated questions answered by voice. Also includes a prompt-improvement tab for dictating rough coding or AI tasks. Everything runs locally — no API keys, no cloud, no internet required.

---

## How it fits together

The three tabs share a single local LLM (Qwen3-14B, AWQ 4-bit quantised, served via vLLM) loaded on first use and kept resident in GPU memory for the rest of the session — it's put to sleep (freeing VRAM, waking back up in a few seconds) after a period of Study-tab inactivity rather than being torn down and reloaded on every action. Speech-to-text uses faster-whisper running on CPU, so the GPU stays free for the language model.

Notes are saved as plain Markdown files under the directory set by `NOTES_DIR` — point this at your Obsidian vault and the notes appear there immediately. The Study tab reads from the same directory. When you designate a "Main note" in the Notes tab, all other notes saved in that session have `[[MainTopic]]` prepended, creating Obsidian backlinks that connect related concepts automatically.

Confidence scores are tracked per note in `data/confidence.json` and feed back into the Study tab's random selection so weaker notes appear more often.

---

## Notes tab

Paste a lecture transcript into the notes tab, then hit **Generate**. The pipeline runs in the background:

1. Identify the lecture subject from the first ~300 words
2. Chunk the transcript at paragraph and sentence boundaries
3. Incremental accumulation — for each chunk, the model decides whether to add a new TOPIC block, enrich an existing block with an example, or skip
4. Exercise extraction — scans for "pause the video" markers and extracts each worked exercise as a separate TOPIC block
5. Verification pass — the model reviews all blocks for internal mathematical consistency and corrects errors
6. Post-processing — strips filler phrases and formatting noise

Output is a set of TOPIC blocks: one per named concept, one per worked exercise. Each block can be:

- **Saved individually** — writes `<NOTES_DIR>/<subject>/<topic>.md`
- **Save All** — saves every block in one go
- **Main note** — toggle on one block to designate it as the session anchor; all other saves in that session prepend `[[AnchorTopic]]` as an Obsidian backlink
- **Copy all** — copies all blocks to the clipboard
- **Delete** — removes a block from the current session without saving

The transcript itself has a **Copy** button so you can keep the raw source alongside the notes.

---

## Study tab

Reads notes from `NOTES_DIR`. Select a subject from the dropdown or let the app choose randomly or by confidence weighting (lower-scoring notes appear more often).

**Question types:**
- **Flashcard** — a concise recall question
- **Extended** — a deeper question that requires explanation

**Answering:**
- Speak your answer and hit Submit — Whisper transcribes it
- Or type directly into the answer box

The local model evaluates your answer against the note content and returns a verdict: Correct, Partial, or Incorrect, with a short explanation of what was missing or wrong.

**Confidence tracking:**
- Each note has a score from 0–100%, stored in `data/confidence.json`
- Correct answer: +10 points (capped at 100%)
- Incorrect: −10 points (floored at 0%)
- Confidence-weighted mode: inverse weighting so weak notes are prioritised

**Exclusions:**
- Exclude notes from the study pool via the Exclusions dialog
- Excluded notes are shown greyed out and can be restored individually

---

## Improve tab

Record a rough spoken task — a coding problem, a feature request, a question to reason through. Hit **Improve** and the app transcribes it and rewrites it as a structured Markdown prompt.

**Modes:**
- **Instruct** — Goal / Requirements / Context format, ready to paste into Claude Code, ChatGPT, etc.
- **Reason** — expands a half-formed thought into connected prose: what you're working out, your reasoning so far, and the question you're left with

**Roles** — select a persona to tailor the output:
- Software Engineer
- Senior Developer
- DevOps Engineer
- ML / Data Scientist
- Full Stack Developer
- Security Engineer

Multiple recordings accumulate in the text box before you hit Improve, which is useful for building up context across several thoughts. Each session is logged to `logs/YYYY-MM-DD.jsonl`.

---

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.12 (required — vLLM's pre-built ROCm wheels are Python-3.12-only) |
| ROCm | 7.1.1 system install (AMD GPU) |
| PyTorch | installed automatically as a dependency of the vLLM ROCm wheel — do not `pip install torch` separately first |
| vLLM | 0.25.1+rocm723 (ROCm build, installed from `https://wheels.vllm.ai/rocm/`) |
| xclip | any |
| libportaudio2 | any |
| libopenmpi3t64 | any (system package — the vLLM ROCm wheel's bundled torch build needs `libmpi_cxx.so.40`) |
| miopen-hip | matching your ROCm version (system package from the ROCm apt repo — needed for `libMIOpen.so.1`) |

**Hardware:** AMD GPU with ROCm support and ≥8 GB VRAM recommended. Tested on RX 7800 XT (16 GB), gfx1100. Whisper runs on CPU — no GPU memory used for transcription. Loading the 14B AWQ model into vLLM takes several minutes the first time (observed ~5 min on this hardware) — this happens once at app startup in a background thread, not on every generation.

---

## Setup

```bash
# 1. Clone
git clone https://github.com/jamess005/Local-AI-Lecture-And-Study-Tool.git
cd Local-AI-Lecture-And-Study-Tool

# 2. Install system dependencies
sudo apt install python3-tk xclip libportaudio2

# 3. Create a virtual environment
python3 -m venv .venv

# 4. Install system libraries the vLLM ROCm wheel needs
sudo apt-get install -y libopenmpi3t64 miopen-hip

# 5. Install vLLM (ROCm build) — pulls in a compatible torch build automatically
.venv/bin/pip install vllm==0.25.1+rocm723 --extra-index-url https://wheels.vllm.ai/rocm/

# 6. Install remaining dependencies
.venv/bin/pip install -r requirements.txt

# 7. Configure
cp .env.example .env
# Edit .env — set MODEL_PATH and NOTES_DIR
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MODEL_PATH` | Yes | — | Path to your local model directory |
| `NOTES_DIR` | No | `~/notes` | Where notes are saved and read from. Point this at your Obsidian vault. |
| `WHISPER_MODEL` | No | `small` | Whisper model size: `tiny`, `base`, `small`, `medium` |

The model is loaded on first use of a tab that needs it (or in the background at app startup) and stays resident in GPU memory across Improve/Notes/Study actions. The Study tab puts it to sleep after 5 minutes of inactivity to free VRAM, waking it back up in a few seconds the next time it's needed.

---

## Running

```bash
# Using the launch script (recommended)
./run.sh

# Or directly
.venv/bin/python3 src/app.py
```

To add a desktop launcher on Linux Mint / GNOME:

```bash
sed "s|/path/to/voiceagent|$(pwd)|g" voiceagent.desktop \
  > ~/.local/share/applications/voiceagent.desktop
```

---

## Docker

The container needs access to your display (X11), your GPU, your microphone, your model weights, and two persistent data directories.

```bash
# Allow the container to connect to your X11 display
xhost +local:docker

docker build -t local-ai-study-tool .

docker run --device=/dev/kfd --device=/dev/dri \
  --device=/dev/snd \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /path/to/models:/models \
  -v /path/to/your/notes:/notes \
  -v /path/to/data:/app/data \
  -e DISPLAY=$DISPLAY \
  local-ai-study-tool
```

**Volume mounts:**

| Host path | Container path | Purpose |
|---|---|---|
| `/path/to/models` | `/models` | LLM weights (matched to `MODEL_PATH=/models`) |
| `/path/to/your/notes` | `/notes` | Notes directory (matched to `NOTES_DIR=/notes`) — persisted between runs |
| `/path/to/data` | `/app/data` | Confidence scores and exclusions — persisted between runs |

Without the notes and data mounts, notes and confidence scores are lost when the container exits.

---

## Data & logs

| Path | Contents |
|---|---|
| `$NOTES_DIR/<subject>/<topic>.md` | Saved notes (Obsidian-compatible Markdown) |
| `data/confidence.json` | Per-note confidence scores |
| `data/exclusions.json` | Notes excluded from the study pool |
| `logs/YYYY-MM-DD.jsonl` | Improve-tab session log |

All data paths are gitignored.

---

## Project structure

```
voiceagent/
├── src/
│   ├── app.py           # Entry point, Improve tab UI
│   ├── notes_tab.py     # Notes generation tab
│   ├── study_tab.py     # Study / Q&A tab
│   ├── improver.py      # LLM inference: note generation, improve, evaluate
│   ├── note_prompts.py  # Prompts for the note generation pipeline
│   ├── study_prompts.py # Prompts for question generation and answer evaluation
│   ├── note_reader.py   # Load saved notes from NOTES_DIR
│   ├── confidence.py    # Per-note confidence tracking and exclusions
│   ├── recorder.py      # Microphone capture (sounddevice)
│   ├── transcriber.py   # Speech-to-text (faster-whisper, CPU)
│   └── logger.py        # Improve-tab session logging
├── run.sh               # Launch script
├── voiceagent.desktop   # Linux desktop entry
├── Dockerfile
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Licence

MIT — see [LICENSE](LICENSE).
