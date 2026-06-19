import os
import random
from pathlib import Path

DEFAULT_NOTES_DIR = os.path.expanduser(os.environ.get("NOTES_DIR", "~/notes"))


def load_notes(notes_dir: str = DEFAULT_NOTES_DIR) -> dict[str, dict[str, dict[str, str]]]:
    """Return {subject: {subtopic: {topic_name: content}}}.

    .md files directly under NOTES_DIR/<subject>/ are grouped under a synthetic
    subtopic keyed by the subject name itself, so notes saved by notes_tab.py
    (which writes flat files) remain visible in the study section.
    """
    notes: dict[str, dict[str, dict[str, str]]] = {}
    base = Path(notes_dir)
    if not base.exists():
        return notes
    for subject_dir in sorted(base.iterdir()):
        if not subject_dir.is_dir() or subject_dir.name.startswith("."):
            continue
        subject = subject_dir.name
        subtopics: dict[str, dict[str, str]] = {}
        flat = {
            f.stem: f.read_text(encoding="utf-8")
            for f in sorted(subject_dir.glob("*.md"))
        }
        if flat:
            subtopics[subject] = flat
        for sub_dir in sorted(subject_dir.iterdir()):
            if not sub_dir.is_dir() or sub_dir.name.startswith("."):
                continue
            topics = {
                f.stem: f.read_text(encoding="utf-8")
                for f in sorted(sub_dir.glob("*.md"))
            }
            if topics:
                subtopics[sub_dir.name] = topics
        if subtopics:
            notes[subject] = subtopics
    return notes


def list_subtopics(subject: str, notes_dir: str = DEFAULT_NOTES_DIR) -> list[str]:
    path = Path(notes_dir) / subject
    if not path.exists():
        return []
    return sorted(d.name for d in path.iterdir() if d.is_dir() and not d.name.startswith("."))


def pick_random_subtopic(
    notes: dict,
    subject: str | None = None,
    subtopic: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, subtopic, combined_content) — all notes in the subtopic joined."""
    def _combine(s: str, st: str) -> str:
        return "\n\n---\n\n".join(notes[s][st].values())

    if subject and subtopic:
        return subject, subtopic, _combine(subject, subtopic)
    if subject:
        st = random.choice(list(notes[subject].keys()))
        return subject, st, _combine(subject, st)
    s, st = random.choice([(s, st) for s, sts in notes.items() for st in sts])
    return s, st, _combine(s, st)


def pick_random_note(
    notes: dict[str, dict[str, dict[str, str]]],
    subject: str | None = None,
    subtopic: str | None = None,
) -> tuple[str, str, str, str]:
    """Return (subject, subtopic, topic_name, content)."""
    if subject and subtopic:
        topic, content = random.choice(list(notes[subject][subtopic].items()))
        return subject, subtopic, topic, content
    if subject:
        pool = [
            (subject, st, t, c)
            for st, topics in notes[subject].items()
            for t, c in topics.items()
        ]
        return random.choice(pool)
    all_topics = [
        (s, st, t, c)
        for s, subs in notes.items()
        for st, topics in subs.items()
        for t, c in topics.items()
    ]
    return random.choice(all_topics)
