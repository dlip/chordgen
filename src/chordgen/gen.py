import csv
from dataclasses import dataclass
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

from chordgen.alt_generator import AltGenerator
from chordgen.assigner import assign_chords
from chordgen.config import GenOptions
from chordgen.scorer import Scorer
from chordgen.chord import build_repertoire, mapping_fingerprints, validate_chords
from chordgen.srs import ProgressFile, learned_words, reconcile_mappings
from chordgen.keyboard_view import resolve_keyboard_layout
from types import SimpleNamespace


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


@dataclass
class GenerationResult:
    chords: list[dict]
    changes: list[str]
    learned_changes: list[str]
    progress: ProgressFile | None


def generate(
    options: GenOptions,
    *,
    progress: ProgressFile | None = None,
    preserve_learned: bool = False,
) -> GenerationResult:
    """Calculate once; the caller previews/confirms before writing anything."""
    scorer = Scorer(options)
    with open(options.file) as f:
        reader = csv.DictReader(f)
        print("Finding and scoring chords")
        chords = [line for line in reader]
        if len(chords) == 0:
            raise Exception("No rows found in chords file")
        original = deepcopy(chords)
        kind, layout = resolve_keyboard_layout(SimpleNamespace(gen=options)) or ("standard", None)
        before_map = build_repertoire(original)
        before = mapping_fingerprints(before_map, kind, layout)
        updated_progress = deepcopy(progress) if progress is not None else None
        if updated_progress is not None:
            reconcile_mappings(updated_progress, before)
        learned = learned_words(updated_progress, before) if updated_progress is not None else set()
        preserve_words = {
            m.base.lower() for m in before_map.values()
            if preserve_learned and m.word in learned
        }
        conflicts = preserve_words & {w.lower() for w in options.ignore_words}
        if conflicts:
            raise ValueError("Cannot preserve ignored learned words: " + ", ".join(sorted(conflicts)))
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

    # Restore protected mappings after alt generation, including explicit
    # overwrite settings. Reservation is runtime-only; frequency stays intact.
    originals = {c["word"].lower(): c for c in original}
    for row in active:
        if row["word"].lower() in preserve_words:
            prior = originals[row["word"].lower()]
            for key in ("chord", "alt1", "alt2", "alt3"):
                row[key] = prior.get(key, "")

    print("Assigning chords")
    assign_chords(active, options, preserve_words=preserve_words)
    chords = _merge_ignored(active, ignored)
    validate_chords(chords)
    after_map = build_repertoire(chords)
    after = mapping_fingerprints(after_map, kind, layout)
    learned_changes = sorted(word for word in learned if before.get(word) != after.get(word))
    changes = []
    for row in chords:
        old = originals.get(row["word"].lower(), {})
        changed = [key for key in ("chord", "alt1", "alt2", "alt3")
                   if old.get(key, "") != row.get(key, "")]
        if changed:
            details = ", ".join(f"{key}: {old.get(key, '')!r} -> {row.get(key, '')!r}" for key in changed)
            changes.append(f"{row['word']}: {details}")
    if updated_progress is not None:
        reconcile_mappings(updated_progress, after)
        # Removed mappings are no longer typeable, but must not regain stale
        # mastery if a later generation happens to recreate them.
        removed = set(before) - set(after)
        for word in removed:
            updated_progress["words"].pop(word, None)
        if removed:
            updated_progress["speed_samples"] = []
            updated_progress["recall_speed_samples"] = []
    return GenerationResult(chords, changes, learned_changes, updated_progress)


def write_chords(options: GenOptions, chords: list[dict]) -> None:
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


def gen(options: GenOptions) -> None:
    """Programmatic generation without a training-progress dependency."""
    result = generate(options)
    write_chords(options, result.chords)
