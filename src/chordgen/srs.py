import json
from pathlib import Path
from typing import TypedDict, Dict
import time

from chordgen.constants import CONFIG_DIR

PROGRESS_FILE = CONFIG_DIR / "progress.json"

class WordProgress(TypedDict):
    correct_in_a_row: int
    last_practiced: float
    next_practice_due: float

Progress = Dict[str, WordProgress]

def load_progress() -> Progress:
    if not PROGRESS_FILE.exists():
        return {}
    with open(PROGRESS_FILE) as f:
        return json.load(f)

def save_progress(progress: Progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def update_progress(progress: Progress, word: str, correct: bool):
    if word not in progress:
        progress[word] = {
            "correct_in_a_row": 0,
            "last_practiced": 0,
            "next_practice_due": time.time(),
        }

    if correct:
        progress[word]["correct_in_a_row"] += 1
    else:
        progress[word]["correct_in_a_row"] = 0

    progress[word]["last_practiced"] = time.time()

    # Simple SRS: double the interval for each correct answer
    correct_streak = progress[word]["correct_in_a_row"]
    if correct_streak > 0:
        interval = 60 * 60 * 24 * (2 ** (correct_streak - 1))  # From 1 day to multiple years
        progress[word]["next_practice_due"] = time.time() + interval
    else:
        progress[word]["next_practice_due"] = time.time() + 60 * 5  # 5 minutes for incorrect words
