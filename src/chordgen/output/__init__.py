from chordgen.chord import Chord


def assigned_rows(chords: list[Chord], limit: int = 0) -> list[Chord]:
    """Select assigned rows in CSV order; zero means unlimited."""
    rows = [row for row in chords if row["chord"]]
    return rows if limit == 0 else rows[:max(0, limit)]
