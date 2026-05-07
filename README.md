# Voice Study Agent

A local desktop study tool with three tabs: generate structured notes from lecture recordings, study them with AI-generated questions and voice answers, and improve rough spoken ideas into clean AI prompts. Runs entirely offline — no API keys, no cloud.

---

## Tabs

### Notes
Record a lecture or paste a transcript, then hit **Generate**. The app sends the transcript through an incremental pipeline that produces structured TOPIC: blocks — one block per concept and one per worked exercise. Save individual notes or all at once as Obsidian-compatible Markdown files under `~/uni/<subject>/`.

### Study
Select a saved note and generate a flashcard or extended question. Answer by voice or text. The app evaluates your answer against the note content and gives a score with feedback.

### Improve
Speak a rough coding or AI task, hit **Improve**. The app transcribes your speech and rewrites it as a structured Markdown prompt (Goal / Requirements / Context). Choose a role persona to tailor the output style.

---

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.11+ |
| ROCm | 7.1 (AMD GPU) |
| PyTorch | 2.4.0+rocm7.1 |
| xclip | any (for clipboard support) |

**Hardware:** AMD GPU with ROCm support and ≥8 GB VRAM recommended (tested on RX 7800 XT with 16 GB). Whisper runs on CPU.

---

## Setup

```bash
# 1. Clone
git clone https://github.com/jamess005/voice-prompt-agent.git
cd voice-prompt-agent

# 2. Install system deps
sudo apt install python3-tk xclip libportaudio2

# 3. Create venv
python3 -m venv .venv

# 4. Install ROCm PyTorch
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/rocm7.1

# 5. Install remaining deps
.venv/bin/pip install -r requirements.txt

# 6. Configure
cp .env.example .env
# Edit .env — set MODEL_PATH to your local model directory
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `MODEL_PATH` | Yes | — | Path to local Qwen 3.5 9B instruct model directory |
| `WHISPER_MODEL` | No | `small` | Whisper model size (`tiny`, `base`, `small`, `medium`) |

---

## Running

```bash
# From terminal
./run.sh

# Or directly
.venv/bin/python3 src/app.py
```

To add it to your application menu (Linux Mint / GNOME):

```bash
cp voiceagent.desktop ~/.local/share/applications/
```

---

## Docker (GPU + display required)

```bash
docker build -t voice-study-agent .

docker run --device=/dev/kfd --device=/dev/dri \
  --device=/dev/snd \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /path/to/models:/models \
  -e DISPLAY=$DISPLAY \
  voice-study-agent
```

---

## Project Structure

```
voice-study-agent/
├── src/
│   ├── app.py           # Entry point, tab layout (customtkinter)
│   ├── notes_tab.py     # Notes generation UI
│   ├── study_tab.py     # Study / Q&A UI
│   ├── improver.py      # LLM inference: note generation, improve, evaluate
│   ├── note_prompts.py  # Prompts for note generation pipeline
│   ├── study_prompts.py # Prompts for question generation and answer evaluation
│   ├── note_reader.py   # Load saved notes from ~/uni/
│   ├── confidence.py    # Per-note confidence tracking
│   ├── recorder.py      # Microphone capture (sounddevice)
│   ├── transcriber.py   # Speech-to-text (faster-whisper, CPU)
│   └── logger.py        # Session logging to logs/YYYY-MM-DD.jsonl
├── run.sh
├── voiceagent.desktop
├── Dockerfile
├── requirements.txt
└── .env                 # Local config (gitignored)
```

---

## Improve — Roles

Select a persona before hitting Improve to tailor the output style:

- Software Engineer
- Senior Developer
- DevOps Engineer
- ML / Data Scientist
- Full Stack Developer
- Security Engineer

---

## Logs

Each session is logged to `logs/YYYY-MM-DD.jsonl` (gitignored). Each entry contains the raw transcription and the improved output with a timestamp.

---

## Licence

MIT — see [LICENSE](LICENSE).
