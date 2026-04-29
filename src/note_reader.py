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
