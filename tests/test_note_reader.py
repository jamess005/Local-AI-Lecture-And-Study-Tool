import pytest
from src.note_reader import load_notes, pick_random_note


@pytest.fixture
def fake_uni(tmp_path):
    # Subject with subdirectory subtopics
    (tmp_path / "Maths").mkdir()
    sub = tmp_path / "Maths" / "Set Theory"
    sub.mkdir()
    (sub / "Sets.md").write_text("A set is a collection.")
    (sub / "Logic.md").write_text("A proposition is true or false.")
    (tmp_path / "Maths" / ".obsidian").mkdir()
    (tmp_path / "Maths" / ".obsidian" / "app.json").write_text("{}")
    # Subject with only flat files (backward-compat: synthetic subtopic = subject name)
    (tmp_path / "Physics").mkdir()
    (tmp_path / "Physics" / "Motion.md").write_text("F = ma")
    # Subject with both flat files and a subdirectory
    (tmp_path / "Chemistry").mkdir()
    (tmp_path / "Chemistry" / "Intro.md").write_text("flat note")
    chem_sub = tmp_path / "Chemistry" / "Reactions"
    chem_sub.mkdir()
    (chem_sub / "Oxidation.md").write_text("loss of electrons")
    return tmp_path


def test_load_notes_groups_by_subject(fake_uni):
    notes = load_notes(str(fake_uni))
    assert set(notes.keys()) == {"Maths", "Physics", "Chemistry"}


def test_load_notes_subdir_creates_subtopic(fake_uni):
    notes = load_notes(str(fake_uni))
    assert "Set Theory" in notes["Maths"]
    assert notes["Maths"]["Set Theory"]["Sets"] == "A set is a collection."


def test_load_notes_flat_files_use_subject_as_subtopic(fake_uni):
    notes = load_notes(str(fake_uni))
    assert "Physics" in notes["Physics"]
    assert notes["Physics"]["Physics"]["Motion"] == "F = ma"


def test_load_notes_mixed_subject_has_both(fake_uni):
    notes = load_notes(str(fake_uni))
    assert "Chemistry" in notes["Chemistry"]          # flat fallback subtopic
    assert "Reactions" in notes["Chemistry"]           # subdir subtopic
    assert notes["Chemistry"]["Chemistry"]["Intro"] == "flat note"
    assert notes["Chemistry"]["Reactions"]["Oxidation"] == "loss of electrons"


def test_load_notes_skips_obsidian(fake_uni):
    notes = load_notes(str(fake_uni))
    assert ".obsidian" not in notes["Maths"]


def test_pick_random_note_with_subject_and_subtopic(fake_uni):
    notes = load_notes(str(fake_uni))
    subject, subtopic, topic, content = pick_random_note(
        notes, subject="Maths", subtopic="Set Theory"
    )
    assert subject == "Maths"
    assert subtopic == "Set Theory"
    assert topic in ("Sets", "Logic")


def test_pick_random_note_from_subject(fake_uni):
    notes = load_notes(str(fake_uni))
    subject, subtopic, topic, content = pick_random_note(notes, subject="Maths")
    assert subject == "Maths"
    assert subtopic == "Set Theory"
    assert topic in ("Sets", "Logic")


def test_pick_random_note_global(fake_uni):
    notes = load_notes(str(fake_uni))
    subject, subtopic, topic, content = pick_random_note(notes)
    assert subject in ("Maths", "Physics", "Chemistry")
