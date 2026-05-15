"""
One-time migration: copy notes from 4 separate subject vaults into a single
combined vault at ~/uni/Semester 1/, prepending [[Subject]] links.

Run from anywhere:
    python tools/migrate_vault.py
"""
from pathlib import Path

SUBJECTS = [
    "Discrete Mathematics",
    "Fundamentals of CS",
    "How Computers Work",
    "Intorduction to Programming",
]
SRC_BASE  = Path.home() / "uni"
DEST_BASE = Path.home() / "uni" / "Semester 1"

def migrate():
    DEST_BASE.mkdir(parents=True, exist_ok=True)
    total = 0

    for subject in SUBJECTS:
        src_dir  = SRC_BASE / subject
        dest_dir = DEST_BASE / subject
        dest_dir.mkdir(parents=True, exist_ok=True)

        index = DEST_BASE / f"{subject}.md"
        if not index.exists():
            index.write_text(f"# {subject}\n", encoding="utf-8")
            print(f"  Created index: {index.name}")

        notes = list(src_dir.glob("*.md"))
        if not notes:
            print(f"  {subject}: no notes found")
            continue

        for src_file in notes:
            content = src_file.read_text(encoding="utf-8")
            link = f"[[{subject}]]"
            if not content.startswith(link):
                content = f"{link}\n\n{content}"
            dest_file = dest_dir / src_file.name
            dest_file.write_text(content, encoding="utf-8")
            total += 1

        print(f"  {subject}: {len(notes)} note(s) copied")

    print(f"\nDone — {total} notes written to {DEST_BASE}")
    print("Next: open ~/uni/Semester 1/ as a new vault in Obsidian,")
    print("      then update NOTES_DIR in .env")

if __name__ == "__main__":
    migrate()
