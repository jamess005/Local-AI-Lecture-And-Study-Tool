# Education Layer Design

**Date:** 2026-04-29
**Status:** Approved

## Context

The voice prompt agent works well for instruction-based and reasoning tasks. This spec adds a Study tab that turns the same tool into an active recall assistant, using the user's existing Obsidian notes (`~/uni/`) as the knowledge base. The goal is to support learning through question generation, spoken answer evaluation, and a confidence tracking system that surfaces weaker topics more often.

No new model is loaded — the existing Qwen 2.5 3B instance is reused for all study operations.

---

## Architecture

### New modules

| File | Responsibility |
|---|---|
| `note_reader.py` | Walk `~/uni/`, skip `.obsidian` dirs, group `.md` files by top-level folder (subject). Return `{subject: {topic_name: content}}`. |
| `confidence.py` | Read/write `data/confidence.json`. One float score (0.0–1.0, default 0.5) per note file path. Update on evaluation result. Weighted random selection for confidence-based topic picking. |
| `study_prompts.py` | System prompt strings for question generation and answer evaluation. Keeps `improver.py` clean. |

### Changes to existing files

| File | Change |
|---|---|
| `improver.py` | Add `generate_question(note_content, style)` and `evaluate_answer(question, note_content, spoken_answer)` methods. Same model, new prompts from `study_prompts.py`. |
| `main.py` | Wrap current UI in a `CTkTabview` — **Prompt** tab (unchanged) and **Study** tab (new). Shared `Recorder`, `Transcriber`, `Improver` instances across both tabs. |

### Shared infrastructure

`Recorder`, `Transcriber`, and `Improver` are instantiated once at app startup (lazy-loaded on first use). The Study tab uses the same instances — no second model load.

---

## Study session flow

### Setup phase (shown on tab open)

1. **Topic selection** — three mutually exclusive options:
   - **Manual** — subject dropdown appears (populated from `note_reader`), user picks a subject; app picks a random note from that subject
   - **Random** — app picks any note uniformly at random
   - **Confidence** — app picks the note with the lowest confidence score (weighted random, lower = higher probability)

2. **Question type** — segmented toggle: **Flashcard** | **Extended**
   - Flashcard: short definition or recall question, expects a brief spoken answer
   - Extended: "explain this concept in your own words", expects a longer answer

3. **Start** — generates a question from the selected note using `generate_question()`

### Session phase

1. Question displayed prominently
2. Source note shown beneath it (small text)
3. **Record** / **Stop** — same behaviour as Prompt tab
4. Answer transcribed via Whisper
5. Transcription sent to `evaluate_answer()` with the question and note content
6. Evaluation result displayed:
   - Verdict: ✓ Correct / ~ Partial / ✗ Incorrect
   - One short paragraph: what was right, what was missing (drawn from the note)
7. Confidence score for that note updates and is shown as a progress bar
8. Two buttons: **Next** (same settings, new question) | **Change topic** (returns to setup phase)

---

## Confidence scoring

- Stored in `data/confidence.json` — gitignored
- Keyed by note file path relative to `~/uni/`
- Default score: `0.5`
- Updates:
  - Correct → `min(score + 0.1, 1.0)`
  - Partial → no change
  - Incorrect → `max(score - 0.1, 0.0)`
- Confidence-based selection: weighted random across all notes, weight = `1.0 - score` (lower confidence = higher weight)

---

## Prompts

### `generate_question(note_content, style)`

**Flashcard system prompt:**
> You are a university tutor. Given the following study note, generate one short flashcard question that tests recall of a specific definition, term, or fact. Output only the question — no preamble, no answer.

**Extended system prompt:**
> You are a university tutor. Given the following study note, generate one question that asks the student to explain a concept in their own words. The question should require a paragraph-length answer. Output only the question — no preamble, no answer.

### `evaluate_answer(question, note_content, spoken_answer)`

**System prompt:**
> You are a university tutor evaluating a student's spoken answer. You have the original study note as ground truth. Assess the answer and respond in exactly this format:
>
> **Verdict:** Correct / Partial / Incorrect
>
> **Feedback:** One short paragraph. State what the student got right, what was missing or wrong, and (if partial/incorrect) what the correct answer is. Draw only from the note content.

---

## Data

```
data/
  confidence.json   # gitignored
docs/
  superpowers/specs/
    2026-04-29-education-layer-design.md
```

Add to `.gitignore`: `data/`

---

## Files changed

| File | Action |
|---|---|
| `main.py` | Add `CTkTabview`, Study tab UI, session state machine |
| `improver.py` | Add `generate_question()` and `evaluate_answer()` methods |
| `note_reader.py` | Create |
| `confidence.py` | Create |
| `study_prompts.py` | Create |
| `.gitignore` | Add `data/` |
| `data/confidence.json` | Created at runtime |

---

## Out of scope (this iteration)

- Web search / external evaluation sources
- Spaced repetition scheduling (SRS intervals) — confidence scoring is the simple first step
- Note editing or annotation from within the app
- Multi-answer sessions (quiz of N questions in sequence before showing results)
