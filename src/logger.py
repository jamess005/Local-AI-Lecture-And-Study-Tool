import json
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")


def log_session(raw: str, improved: str) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "raw": raw,
        "improved": improved,
    }
    date_str = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(LOG_DIR, f"{date_str}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
