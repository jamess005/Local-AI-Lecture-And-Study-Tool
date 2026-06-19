import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
CONFIDENCE_FILE = DATA_DIR / "confidence.json"
EXCLUSIONS_FILE = DATA_DIR / "exclusions.json"


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
    notes: dict[str, dict[str, dict[str, str]]], scores: dict[str, float]
) -> tuple[str, str, str, str]:
    """Weighted random pick: lower confidence = higher selection weight."""
    all_topics = [
        (s, st, t, c)
        for s, subs in notes.items()
        for st, topics in subs.items()
        for t, c in topics.items()
    ]
    weights = [1.0 - get_score(scores, f"{s}/{st}/{t}") for s, st, t, _ in all_topics]
    if all(w == 0.0 for w in weights):
        weights = [1.0] * len(weights)
    return random.choices(all_topics, weights=weights, k=1)[0]


def score_key(subject: str, subtopic: str, topic: str) -> str:
    return f"{subject}/{subtopic}/{topic}"


def load_exclusions() -> set[str]:
    if not EXCLUSIONS_FILE.exists():
        return set()
    return set(json.loads(EXCLUSIONS_FILE.read_text(encoding="utf-8")))


def save_exclusions(excluded: set[str]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    EXCLUSIONS_FILE.write_text(json.dumps(sorted(excluded), indent=2), encoding="utf-8")
