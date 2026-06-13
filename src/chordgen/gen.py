import csv
import logging
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

from chordgen.alt_generator import AltGenerator
from chordgen.assigner import assign_chords
from chordgen.config import Config, GenOptions
from chordgen.scorer import Scorer


def _split_ignored(
    chords: list[dict[str, str]], ignore_words: list[str]
) -> tuple[list[dict[str, str]], list[tuple[int, dict[str, str]]]]:
    """Separate rows whose word appears in ``ignore_words``.

    Returns ``(active_rows, [(original_index, ignored_row), ...])``. The
    ignored rows are kept out of scoring/assignment but merged back into
    the final CSV so they remain in the word list as unchorded words.
    """
    if not ignore_words:
        return chords, []
    ignored_set = {w.lower() for w in ignore_words}
    active: list[dict[str, str]] = []
    ignored: list[tuple[int, dict[str, str]]] = []
    for i, c in enumerate(chords):
        if c.get("word", "").lower() in ignored_set:
            ignored.append((i, c))
        else:
            active.append(c)
    if ignored:
        print(f"Ignoring {len(ignored)} words during chord assignment")
    return active, ignored


def _merge_ignored(
    active: list[dict[str, str]],
    ignored: list[tuple[int, dict[str, str]]],
) -> list[dict[str, str]]:
    """Merge ignored rows back into their original positions."""
    if not ignored:
        return active
    result: list[dict[str, str]] = []
    active_iter = iter(active)
    ignored_iter = iter(ignored)
    next_ignored = next(ignored_iter, None)
    for i in range(len(active) + len(ignored)):
        if next_ignored is not None and next_ignored[0] == i:
            # Clear any leftover chord/alts from a previous run.
            row = next_ignored[1]
            row["chord"] = ""
            row["alt1"] = ""
            row["alt2"] = ""
            row["alt3"] = ""
            if "debug" in row:
                row["debug"] = ""
            result.append(row)
            next_ignored = next(ignored_iter, None)
        else:
            result.append(next(active_iter))
    return result


def gen(options: GenOptions) -> None:
    scorer = Scorer(options)
    with open(options.file) as f:
        reader = csv.DictReader(f)
        print("Finding and scoring chords")
        chords = [line for line in reader]
        if len(chords) == 0:
            raise Exception("No rows found in chords file")
        active, ignored = _split_ignored(chords, options.ignore_words)
        with ProcessPoolExecutor() as executor:
            active = list(
                tqdm(
                    executor.map(scorer.score, active, chunksize=10),
                    total=len(active),
                )
            )

    print("Generating alts")
    alt_generator = AltGenerator(options)
    with ProcessPoolExecutor() as executor:
        active = list(
            tqdm(
                executor.map(alt_generator.add_alt, active, chunksize=10),
                total=len(active),
            )
        )

    print("Assigning chords")
    assign_chords(active, options)

    chords = _merge_ignored(active, ignored)

    print(f"Writing {options.file}")
    with open(options.file, "w", newline="") as f:
        # Union of every row's keys (rows read from existing CSVs may
        # have differing columns). Preserve first-row ordering and
        # append any extras seen later. The `debug` column is included
        # only when options.debug is set; when disabled we also drop
        # any stale debug values left over from a previous run.
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in chords:
            for k in row.keys():
                if k not in seen and k != "options":
                    seen.add(k)
                    fieldnames.append(k)
        if options.debug:
            if "debug" not in seen:
                fieldnames.append("debug")
        else:
            if "debug" in fieldnames:
                fieldnames.remove("debug")
            for row in chords:
                if "debug" in row:
                    row["debug"] = ""
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(chords)
