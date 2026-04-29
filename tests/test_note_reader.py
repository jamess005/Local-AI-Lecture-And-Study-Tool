import pytest
from pathlib import Path
from src.note_reader import load_notes, pick_random_note

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
