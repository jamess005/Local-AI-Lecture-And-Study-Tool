# Education Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Study tab to the voice prompt agent that generates questions from the user's Obsidian notes, evaluates spoken answers, and tracks confidence per topic over time.

**Architecture:** A `CTkTabview` wraps the existing Prompt UI (untouched) and a new Study tab backed by `StudyTab` in `study_tab.py`. All three new data modules (`note_reader`, `confidence`, `study_prompts`) are pure functions with no UI coupling. The existing `Improver` instance is reused for question generation and evaluation via two new methods that share a refactored `_generate()` helper.

**Tech Stack:** Python 3.12, customtkinter, Qwen 2.5 3B (already loaded), faster-whisper (already loaded), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `note_reader.py` | Create | Walk `~/uni/`, return `{subject: {topic: content}}` |
| `confidence.py` | Create | Read/write `data/confidence.json`, scoring, weighted pick |
| `study_prompts.py` | Create | System prompt strings for question gen + evaluation |
| `improver.py` | Modify | Extract `_generate()`, add `generate_question()` + `evaluate_answer()` |
| `study_tab.py` | Create | Full Study tab UI + session state machine |
| `main.py` | Modify | Wrap existing UI in `CTkTabview`, mount `StudyTab` |
| `tests/test_note_reader.py` | Create | Unit tests for note loading |
| `tests/test_confidence.py` | Create | Unit tests for scoring + selection |
| `.gitignore` | Modify | Add `data/` |

---

## Task 1: note_reader.py

**Files:**
- Create: `note_reader.py`
- Create: `tests/test_note_reader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_note_reader.py
import pytest
from pathlib import Path
from note_reader import load_notes, pick_random_note

@pytest.fixture
def fake_uni(tmp_path):
    (tmp_path / "Maths").mkdir()
    (tmp_path / "Maths" / "Sets.md").write_text("A set is a collection.")
    (tmp_path / "Maths" / "Logic.md").write_text("A proposition is true or false.")
    (tmp_path / "Maths" / ".obsidian").mkdir()
    (tmp_path / "Maths" / ".obsidian" / "app.json").write_text("{}")
    (tmp_path / "Physics").mkdir()
    (tmp_path / "Physics" / "Motion.md").write_text("F = ma")
    return tmp_path

def test_load_notes_groups_by_subject(fake_uni):
    notes = load_notes(str(fake_uni))
    assert set(notes.keys()) == {"Maths", "Physics"}

def test_load_notes_reads_content(fake_uni):
    notes = load_notes(str(fake_uni))
    assert notes["Maths"]["Sets"] == "A set is a collection."

def test_load_notes_skips_obsidian(fake_uni):
    notes = load_notes(str(fake_uni))
    assert ".obsidian" not in notes["Maths"]

def test_pick_random_note_from_subject(fake_uni):
    notes = load_notes(str(fake_uni))
    subject, topic, content = pick_random_note(notes, subject="Maths")
    assert subject == "Maths"
    assert topic in ("Sets", "Logic")

def test_pick_random_note_global(fake_uni):
    notes = load_notes(str(fake_uni))
    subject, topic, content = pick_random_note(notes)
    assert subject in ("Maths", "Physics")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd ~/ml-proj/voiceagent && .venv/bin/pytest tests/test_note_reader.py -v
```
Expected: `ModuleNotFoundError: No module named 'note_reader'`

- [ ] **Step 3: Implement note_reader.py**

```python
# note_reader.py
import os
import random
from pathlib import Path

DEFAULT_NOTES_DIR = os.path.expanduser("~/uni")


def load_notes(notes_dir: str = DEFAULT_NOTES_DIR) -> dict[str, dict[str, str]]:
    """Return {subject: {topic_name: content}} from a directory of Obsidian vaults."""
    notes: dict[str, dict[str, str]] = {}
    base = Path(notes_dir)
    if not base.exists():
        return notes
    for subject_dir in sorted(base.iterdir()):
        if not subject_dir.is_dir() or subject_dir.name.startswith("."):
            continue
        topics: dict[str, str] = {}
        for md_file in sorted(subject_dir.glob("*.md")):
            topics[md_file.stem] = md_file.read_text(encoding="utf-8")
        if topics:
            notes[subject_dir.name] = topics
    return notes


def pick_random_note(
    notes: dict[str, dict[str, str]], subject: str | None = None
) -> tuple[str, str, str]:
    """Return (subject, topic_name, content). Picks randomly from subject or globally."""
    if subject:
        topic, content = random.choice(list(notes[subject].items()))
        return subject, topic, content
    all_topics = [
        (s, t, c) for s, topics in notes.items() for t, c in topics.items()
    ]
    return random.choice(all_topics)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_note_reader.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add note_reader.py tests/test_note_reader.py
git commit -m "feat: add note_reader — loads Obsidian notes by subject"
```

---

## Task 2: confidence.py

**Files:**
- Create: `confidence.py`
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_confidence.py
import pytest
from confidence import get_score, update_score, pick_by_confidence

def test_get_score_default():
    assert get_score({}, "Maths/Sets") == 0.5

def test_get_score_existing():
    assert get_score({"Maths/Sets": 0.8}, "Maths/Sets") == 0.8

def test_update_correct_increases():
    scores = {"Maths/Sets": 0.5}
    result = update_score(scores, "Maths/Sets", "Correct")
    assert result["Maths/Sets"] == pytest.approx(0.6)

def test_update_incorrect_decreases():
    scores = {"Maths/Sets": 0.5}
    result = update_score(scores, "Maths/Sets", "Incorrect")
    assert result["Maths/Sets"] == pytest.approx(0.4)

def test_update_partial_unchanged():
    scores = {"Maths/Sets": 0.5}
    result = update_score(scores, "Maths/Sets", "Partial")
    assert result["Maths/Sets"] == pytest.approx(0.5)

def test_update_clamps_at_one():
    scores = {"Maths/Sets": 1.0}
    result = update_score(scores, "Maths/Sets", "Correct")
    assert result["Maths/Sets"] == 1.0

def test_update_clamps_at_zero():
    scores = {"Maths/Sets": 0.0}
    result = update_score(scores, "Maths/Sets", "Incorrect")
    assert result["Maths/Sets"] == 0.0

def test_pick_by_confidence_returns_tuple():
    notes = {"Maths": {"Sets": "content"}}
    scores = {}
    subject, topic, content = pick_by_confidence(notes, scores)
    assert subject == "Maths"
    assert topic == "Sets"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
.venv/bin/pytest tests/test_confidence.py -v
```
Expected: `ModuleNotFoundError: No module named 'confidence'`

- [ ] **Step 3: Implement confidence.py**

```python
# confidence.py
import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CONFIDENCE_FILE = DATA_DIR / "confidence.json"


def load_scores() -> dict[str, float]:
    if not CONFIDENCE_FILE.exists():
        return {}
    return json.loads(CONFIDENCE_FILE.read_text(encoding="utf-8"))


def save_scores(scores: dict[str, float]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    CONFIDENCE_FILE.write_text(json.dumps(scores, indent=2), encoding="utf-8")


def get_score(scores: dict[str, float], key: str) -> float:
    return scores.get(key, 0.5)


def update_score(scores: dict[str, float], key: str, verdict: str) -> dict[str, float]:
    current = get_score(scores, key)
    if verdict == "Correct":
        scores[key] = min(round(current + 0.1, 10), 1.0)
    elif verdict == "Incorrect":
        scores[key] = max(round(current - 0.1, 10), 0.0)
    return scores


def pick_by_confidence(
    notes: dict[str, dict[str, str]], scores: dict[str, float]
) -> tuple[str, str, str]:
    """Weighted random pick: lower confidence score = higher selection weight."""
    all_topics = [
        (s, t, c) for s, topics in notes.items() for t, c in topics.items()
    ]
    weights = [1.0 - get_score(scores, f"{s}/{t}") for s, t, c in all_topics]
    # Avoid all-zero weights (all scores at 1.0)
    if all(w == 0.0 for w in weights):
        weights = [1.0] * len(weights)
    return random.choices(all_topics, weights=weights, k=1)[0]


def score_key(subject: str, topic: str) -> str:
    return f"{subject}/{topic}"
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
.venv/bin/pytest tests/test_confidence.py -v
```
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add confidence.py tests/test_confidence.py
git commit -m "feat: add confidence tracker with weighted topic selection"
```

---

## Task 3: study_prompts.py

**Files:**
- Create: `study_prompts.py`

- [ ] **Step 1: Create study_prompts.py**

```python
# study_prompts.py

FLASHCARD_QUESTION = """\
You are a university tutor. Given the following study note, generate one short \
flashcard question that tests recall of a specific definition, term, or fact. \
Output only the question — no preamble, no answer."""

EXTENDED_QUESTION = """\
You are a university tutor. Given the following study note, generate one question \
that asks the student to explain a concept in their own words. The question should \
require a paragraph-length answer. Output only the question — no preamble, no answer."""

EVALUATE_ANSWER = """\
You are a university tutor evaluating a student's spoken answer. \
You have the original study note as ground truth. \
Assess the answer and respond in exactly this format:

**Verdict:** Correct / Partial / Incorrect

**Feedback:** One short paragraph. State what the student got right, what was \
missing or wrong, and (if partial/incorrect) what the correct answer is. \
Draw only from the note content."""
```

- [ ] **Step 2: Commit**

```bash
git add study_prompts.py
git commit -m "feat: add study prompt strings for question gen and evaluation"
```

---

## Task 4: Refactor improver.py — extract _generate(), add study methods

**Files:**
- Modify: `improver.py`

- [ ] **Step 1: Extract `_generate()` and add study methods**

Replace the `improve()` method body and add two new methods. The full updated class body after `load()`:

```python
    def improve(self, raw_text: str, role: str = "Software Engineer", mode: str = "Instruct") -> str:
        from improver import ROLE_PROMPTS, MODE_FORMATS
        persona = ROLE_PROMPTS.get(role, ROLE_PROMPTS["Software Engineer"])
        fmt = MODE_FORMATS.get(mode, MODE_FORMATS["Instruct"])
        system = persona + "\n\n" + fmt
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": raw_text},
        ]
        return self._generate(messages, max_new_tokens=512)

    def generate_question(self, note_content: str, style: str = "Flashcard") -> str:
        from study_prompts import FLASHCARD_QUESTION, EXTENDED_QUESTION
        system = FLASHCARD_QUESTION if style == "Flashcard" else EXTENDED_QUESTION
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": note_content},
        ]
        return self._generate(messages, max_new_tokens=128)

    def evaluate_answer(self, question: str, note_content: str, spoken_answer: str) -> str:
        from study_prompts import EVALUATE_ANSWER
        user_content = (
            f"Question: {question}\n\n"
            f"Note:\n{note_content}\n\n"
            f"Student's answer: {spoken_answer}"
        )
        messages = [
            {"role": "system", "content": EVALUATE_ANSWER},
            {"role": "user", "content": user_content},
        ]
        return self._generate(messages, max_new_tokens=256)

    def _generate(self, messages: list[dict], max_new_tokens: int = 512) -> str:
        if self._model is None:
            raise RuntimeError("Model not loaded")
        text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer([text], return_tensors="pt").to("cuda")
        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()
```

- [ ] **Step 2: Verify app still launches cleanly (smoke test)**

```bash
cd ~/ml-proj/voiceagent && .venv/bin/python3 -c "
from improver import Improver
i = Improver()
print('Improver OK — methods:', [m for m in dir(i) if not m.startswith('__')])
"
```
Expected output includes: `_generate`, `evaluate_answer`, `generate_question`, `improve`, `load`

- [ ] **Step 3: Commit**

```bash
git add improver.py
git commit -m "refactor: extract _generate(), add generate_question and evaluate_answer"
```

---

## Task 5: study_tab.py — setup phase

**Files:**
- Create: `study_tab.py`

- [ ] **Step 1: Create study_tab.py with setup phase UI**

```python
# study_tab.py
import threading
import customtkinter as ctk

from note_reader import load_notes, pick_random_note
from confidence import load_scores, save_scores, update_score, pick_by_confidence, score_key

SETUP = "setup"
GENERATING = "generating"
READY = "ready"
RECORDING = "recording"
EVALUATING = "evaluating"
RESULT = "result"


class StudyTab:
    def __init__(self, parent: ctk.CTkFrame, recorder, transcriber, improver):
        self._recorder = recorder
        self._transcriber = transcriber
        self._improver = improver
        self._notes: dict = {}
        self._scores: dict = {}
        self._current: tuple | None = None   # (subject, topic, content)
        self._current_question: str = ""
        self._selection_mode: str = "Manual"
        self._state: str = SETUP

        self._load_data()
        self._build_ui(parent)
        self._show_setup()

    def _load_data(self):
        self._notes = load_notes()
        self._scores = load_scores()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self, parent: ctk.CTkFrame):
        self._frame = ctk.CTkFrame(parent, fg_color="transparent")
        self._frame.pack(fill="both", expand=True, padx=12, pady=12)

        # Status
        self._status = ctk.CTkLabel(
            self._frame, text="", font=("Helvetica", 12), text_color="gray"
        )
        self._status.pack(anchor="w", pady=(0, 6))

        # ── Setup widgets ────────────────────────────────────────────────────
        self._setup_frame = ctk.CTkFrame(self._frame, fg_color="transparent")

        ctk.CTkLabel(
            self._setup_frame, text="Topic selection", font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(0, 4))

        sel_row = ctk.CTkFrame(self._setup_frame, fg_color="transparent")
        sel_row.pack(anchor="w", pady=(0, 8))

        self._sel_var = ctk.StringVar(value="Manual")
        for mode in ("Manual", "Random", "Confidence"):
            ctk.CTkRadioButton(
                sel_row, text=mode, variable=self._sel_var, value=mode,
                command=self._on_selection_mode_change, font=("Helvetica", 12),
            ).pack(side="left", padx=6)

        self._subject_var = ctk.StringVar()
        subjects = list(self._notes.keys()) or ["(no notes found)"]
        self._subject_var.set(subjects[0])
        self._subject_menu = ctk.CTkOptionMenu(
            self._setup_frame, values=subjects, variable=self._subject_var,
            width=240, font=("Helvetica", 12),
        )
        self._subject_menu.pack(anchor="w", pady=(0, 12))

        ctk.CTkLabel(
            self._setup_frame, text="Question type", font=("Helvetica", 13, "bold")
        ).pack(anchor="w", pady=(0, 4))
        self._qtype_var = ctk.StringVar(value="Flashcard")
        ctk.CTkSegmentedButton(
            self._setup_frame, values=["Flashcard", "Extended"],
            variable=self._qtype_var, width=200, font=("Helvetica", 12),
        ).pack(anchor="w", pady=(0, 16))

        self._start_btn = ctk.CTkButton(
            self._setup_frame, text="Start →", width=140, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_start,
        )
        self._start_btn.pack(anchor="w")

        # ── Session widgets ──────────────────────────────────────────────────
        self._session_frame = ctk.CTkFrame(self._frame, fg_color="transparent")

        self._question_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 15, "bold"),
            wraplength=580, justify="left",
        )
        self._question_label.pack(anchor="w", pady=(0, 4))

        self._source_label = ctk.CTkLabel(
            self._session_frame, text="", font=("Helvetica", 11),
            text_color="gray",
        )
        self._source_label.pack(anchor="w", pady=(0, 12))

        # Record / Stop
        self._record_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        self._record_row.pack(anchor="w", pady=(0, 12))

        self._record_btn = ctk.CTkButton(
            self._record_row, text="● Record", width=130, height=44,
            font=("Helvetica", 14, "bold"), command=self._on_record,
        )
        self._record_btn.pack(side="left", padx=(0, 8))
        self._stop_btn = ctk.CTkButton(
            self._record_row, text="■ Stop", width=110, height=44,
            font=("Helvetica", 14, "bold"), fg_color="#2980b9",
            command=self._on_stop,
        )
        self._stop_btn.pack(side="left")
        self._stop_btn.pack_forget()

        # Evaluation result
        self._result_box = ctk.CTkTextbox(
            self._session_frame, width=580, height=160,
            font=("Helvetica", 13), wrap="word", state="disabled",
        )
        self._result_box.pack(pady=(0, 8))
        self._result_box.pack_forget()

        # Confidence bar
        self._conf_frame = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        ctk.CTkLabel(
            self._conf_frame, text="Confidence:", font=("Helvetica", 11)
        ).pack(side="left", padx=(0, 6))
        self._conf_bar = ctk.CTkProgressBar(self._conf_frame, width=200)
        self._conf_bar.set(0.5)
        self._conf_bar.pack(side="left")
        self._conf_label = ctk.CTkLabel(
            self._conf_frame, text="50%", font=("Helvetica", 11)
        )
        self._conf_label.pack(side="left", padx=(6, 0))

        # Next / Change topic
        self._nav_row = ctk.CTkFrame(self._session_frame, fg_color="transparent")
        self._next_btn = ctk.CTkButton(
            self._nav_row, text="Next →", width=110, height=40,
            command=self._on_next,
        )
        self._next_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            self._nav_row, text="Change topic", width=130, height=40,
            fg_color="#555", command=self._show_setup,
        ).pack(side="left")

    def _on_selection_mode_change(self):
        if self._sel_var.get() == "Manual":
            self._subject_menu.pack(anchor="w", pady=(0, 12))
        else:
            self._subject_menu.pack_forget()

    # ── Phase transitions ────────────────────────────────────────────────────

    def _show_setup(self):
        self._session_frame.pack_forget()
        self._setup_frame.pack(fill="both", expand=True)
        self._state = SETUP
        self._status.configure(text="Choose a topic and question type")
        if self._sel_var.get() != "Manual":
            self._subject_menu.pack_forget()

    def _show_session(self):
        self._setup_frame.pack_forget()
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 8))
        self._session_frame.pack(fill="both", expand=True)

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _on_start(self):
        if not self._notes:
            self._status.configure(text="No notes found in ~/uni/")
            return
        mode = self._sel_var.get()
        if mode == "Manual":
            subject = self._subject_var.get()
            self._current = pick_random_note(self._notes, subject=subject)
        elif mode == "Random":
            self._current = pick_random_note(self._notes)
        else:
            self._current = pick_by_confidence(self._notes, self._scores)

        self._show_session()
        self._generate_question()

    def _generate_question(self):
        self._state = GENERATING
        self._status.configure(text="Generating question...")
        self._record_btn.configure(state="disabled")
        subject, topic, content = self._current
        style = self._qtype_var.get()
        threading.Thread(
            target=self._do_generate, args=(content, style), daemon=True
        ).start()

    def _do_generate(self, content: str, style: str):
        question = self._improver.generate_question(content, style)
        self._frame.after(0, lambda: self._on_question_ready(question))

    def _on_question_ready(self, question: str):
        subject, topic, _ = self._current
        self._current_question = question
        self._question_label.configure(text=question)
        self._source_label.configure(text=f"{subject} › {topic}")
        key = score_key(subject, topic)
        score = self._scores.get(key, 0.5)
        self._conf_bar.set(score)
        self._conf_label.configure(text=f"{int(score * 100)}%")
        self._state = READY
        self._status.configure(text="Record your answer")
        self._record_btn.configure(state="normal")

    def _on_record(self):
        self._state = RECORDING
        self._record_btn.pack_forget()
        self._stop_btn.pack(side="left")
        self._status.configure(text="Recording...")
        self._recorder.start()

    def _on_stop(self):
        if self._state != RECORDING:
            return
        self._state = EVALUATING
        audio = self._recorder.stop()
        self._stop_btn.pack_forget()
        self._record_btn.pack(side="left", padx=(0, 8))
        self._record_btn.configure(state="disabled")
        self._status.configure(text="Transcribing...")
        threading.Thread(
            target=self._do_transcribe_and_evaluate, args=(audio,), daemon=True
        ).start()

    def _do_transcribe_and_evaluate(self, audio):
        text = self._transcriber.transcribe(audio)
        self._frame.after(0, lambda: self._status.configure(text="Evaluating..."))
        _, _, content = self._current
        result = self._improver.evaluate_answer(
            self._current_question, content, text
        )
        self._frame.after(0, lambda: self._on_result(result))

    def _on_result(self, result: str):
        subject, topic, _ = self._current
        key = score_key(subject, topic)

        # Parse verdict from result text
        verdict = "Partial"
        for line in result.splitlines():
            if "Verdict:" in line:
                if "Correct" in line and "Incorrect" not in line:
                    verdict = "Correct"
                elif "Incorrect" in line:
                    verdict = "Incorrect"
                break

        self._scores = update_score(self._scores, key, verdict)
        threading.Thread(
            target=save_scores, args=(self._scores,), daemon=True
        ).start()

        score = self._scores.get(key, 0.5)
        self._conf_bar.set(score)
        self._conf_label.configure(text=f"{int(score * 100)}%")

        self._result_box.configure(state="normal")
        self._result_box.delete("1.0", "end")
        self._result_box.insert("1.0", result)
        self._result_box.configure(state="disabled")
        self._result_box.pack(pady=(0, 8))
        self._conf_frame.pack(anchor="w", pady=(0, 8))
        self._nav_row.pack(anchor="w")

        self._state = RESULT
        self._status.configure(text="")
        self._record_btn.configure(state="normal")

    def _on_next(self):
        self._result_box.pack_forget()
        self._conf_frame.pack_forget()
        self._nav_row.pack_forget()
        mode = self._sel_var.get()
        if mode == "Manual":
            subject = self._subject_var.get()
            self._current = pick_random_note(self._notes, subject=subject)
        elif mode == "Random":
            self._current = pick_random_note(self._notes)
        else:
            self._current = pick_by_confidence(self._notes, self._scores)
        self._generate_question()
```

- [ ] **Step 2: Verify syntax**

```bash
cd ~/ml-proj/voiceagent && .venv/bin/python3 -c "import study_tab; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add study_tab.py
git commit -m "feat: add StudyTab with setup phase, session flow, and evaluation UI"
```

---

## Task 6: main.py — wrap in CTkTabview, mount StudyTab

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add import at top of main.py**

Add after the existing imports:

```python
from study_tab import StudyTab
```

- [ ] **Step 2: Update `__init__` to create shared tab view**

Replace `self._build_ui()` call in `__init__` with:

```python
        self._build_ui()
```

No change needed there — the tab structure is built inside `_build_ui`.

- [ ] **Step 3: Rewrite `_build_ui` to use CTkTabview**

Replace the entire `_build_ui` method:

```python
    def _build_ui(self):
        self._tabs = ctk.CTkTabview(self, anchor="nw")
        self._tabs.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Prompt tab ───────────────────────────────────────────────────────
        prompt_tab = self._tabs.add("Prompt")

        top = ctk.CTkFrame(prompt_tab, fg_color="transparent")
        top.pack(fill="x", padx=4, pady=(8, 4))

        self._status = ctk.CTkLabel(top, text="Ready", font=("Helvetica", 13), anchor="w")
        self._status.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(top, text="Mode:", font=("Helvetica", 12)).pack(side="left", padx=(8, 4))
        self._mode_var = ctk.StringVar(value=MODES[0])
        ctk.CTkSegmentedButton(
            top, values=MODES, variable=self._mode_var,
            font=("Helvetica", 12), width=180,
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(top, text="Role:", font=("Helvetica", 12)).pack(side="left", padx=(0, 4))
        self._role_var = ctk.StringVar(value=ROLES[0])
        self._role_menu = ctk.CTkOptionMenu(
            top, values=ROLES, variable=self._role_var, width=180,
            font=("Helvetica", 12),
        )
        self._role_menu.pack(side="left")

        self._textbox = ctk.CTkTextbox(
            prompt_tab, font=("Helvetica", 13), wrap="word",
        )
        self._textbox.pack(fill="both", expand=True, padx=4, pady=(4, 8))

        self._btn_frame = ctk.CTkFrame(prompt_tab, fg_color="transparent")
        self._btn_frame.pack(pady=(0, 8))

        self._record_btn = ctk.CTkButton(
            self._btn_frame, text="● Record", width=140, height=44,
            font=("Helvetica", 15, "bold"), command=self._on_record,
        )
        self._stop_btn = ctk.CTkButton(
            self._btn_frame, text="■ Stop", width=120, height=44,
            font=("Helvetica", 15, "bold"), fg_color="#2980b9",
            command=self._on_stop,
        )
        self._cancel_btn = ctk.CTkButton(
            self._btn_frame, text="Cancel", width=100, height=44,
            fg_color="#555", command=self._on_cancel,
        )
        self._improve_btn = ctk.CTkButton(
            self._btn_frame, text="Improve →", width=120, height=44,
            command=self._on_improve,
        )
        self._clear_btn = ctk.CTkButton(
            self._btn_frame, text="Clear", width=80, height=44,
            fg_color="#555", command=self._on_clear,
        )
        self._copy_btn = ctk.CTkButton(
            self._btn_frame, text="Copy", width=80, height=44,
            command=self._on_copy,
        )
        self._set_idle_buttons()

        # ── Study tab ────────────────────────────────────────────────────────
        study_tab = self._tabs.add("Study")
        StudyTab(study_tab, self._recorder, self._transcriber, self._improver)
```

- [ ] **Step 4: Launch app and verify both tabs appear**

```bash
cd ~/ml-proj/voiceagent && .venv/bin/python3 main.py
```

Expected: App opens with "Prompt" and "Study" tabs. Prompt tab works as before. Study tab shows setup UI.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: wrap app in CTkTabview, mount StudyTab on Study tab"
```

---

## Task 7: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add data/ to .gitignore**

Add to the end of `.gitignore`:

```
# Confidence scores (personal data)
data/
```

- [ ] **Step 2: Commit and push**

```bash
git add .gitignore
git commit -m "chore: gitignore data/ directory for confidence scores"
git push
```

---

## Self-Review

**Spec coverage check:**
- ✓ `note_reader.py` — Task 1
- ✓ `confidence.py` with weighted pick — Task 2
- ✓ `study_prompts.py` — Task 3
- ✓ `improver.generate_question()` + `evaluate_answer()` + `_generate()` — Task 4
- ✓ Setup phase (Manual/Random/Confidence, Flashcard/Extended, Start) — Task 5
- ✓ Session phase (question display, record/stop, evaluation, confidence bar, Next/Change topic) — Task 5
- ✓ `CTkTabview` with Prompt + Study tabs — Task 6
- ✓ `data/` gitignored — Task 7

**Placeholder scan:** No TBDs, no "handle appropriately", no forward references to undefined types. ✓

**Type consistency:**
- `score_key(subject, topic)` defined in `confidence.py`, used in `study_tab.py` via import ✓
- `pick_random_note(notes, subject=...)` signature matches usage in `_on_start` and `_on_next` ✓
- `self._current` is always `(subject, topic, content)` tuple — set in `_on_start`/`_on_next`, unpacked consistently ✓
- `self._improver.generate_question(content, style)` / `evaluate_answer(question, content, answer)` match Task 4 signatures ✓
