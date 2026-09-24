"""Read-only personal-text coverage and practice difficulty reports."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import statistics

from chordgen.book import Book
from chordgen.chord import Chord, PracticeMapping, build_repertoire, mapping_fingerprints
from chordgen.srs import ProgressFile, learned_words, progress_entry_error


RECALL_MIN_SAMPLES = 3


def recall_samples(entry: dict) -> list[float]:
    samples = []
    for sample in entry.get("recall_seconds", []):
        if type(sample) not in (int, float):
            continue
        try:
            value = float(sample)
        except OverflowError:
            continue
        if math.isfinite(value) and value > 0:
            samples.append(value)
    return samples


@dataclass(frozen=True)
class Recommendation:
    word: str
    forms: tuple[str, ...]
    tokens: int
    prerequisite: bool


@dataclass(frozen=True)
class RecallComparison:
    word: str
    tokens: int
    samples: int
    recall_seconds: float
    baseline_seconds: float

    @property
    def estimated_seconds_saved(self) -> float:
        return self.tokens * (self.baseline_seconds - self.recall_seconds)


@dataclass
class TextAnalysis:
    total_tokens: int
    unique_words: int
    primary_tokens: int
    alt_tokens: int
    learned_tokens: int
    uncovered: list[tuple[str, int]]
    unlearned: list[tuple[str, int]]
    recommendations: list[Recommendation]
    comparisons: list[RecallComparison]
    unmeasured_tokens: int
    legacy_cards: int


def analyze_text(
    book: Book,
    chords: list[Chord],
    progress: ProgressFile,
    *,
    keyboard_kind: str = "standard",
    keyboard_layout: list[list[str]] | None = None,
    limit: int = 20,
    baseline_wpm: float | None = None,
) -> TextAnalysis:
    """Count normalized word tokens once, never modifying source or progress.

    Recommendations group unlearned alts behind a needed base. Their token
    counts are potential coverage after learning the listed forms, not credit
    for mastering all modifiers when only the base has been learned.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    if baseline_wpm is not None and (not math.isfinite(baseline_wpm) or baseline_wpm <= 0):
        raise ValueError("baseline WPM must be finite and positive")
    counts = Counter(t.word_key for t in book.tokens if t.is_word and t.word_key)
    repertoire = build_repertoire(chords)
    fingerprints = mapping_fingerprints(repertoire, keyboard_kind, keyboard_layout)
    learned = {word.lower() for word in learned_words(progress, fingerprints)}
    uncovered = sorted(((w, n) for w, n in counts.items() if w not in repertoire),
                       key=lambda pair: (-pair[1], pair[0]))
    unlearned = sorted(((w, n) for w, n in counts.items() if w in repertoire and w not in learned),
                       key=lambda pair: (-pair[1], pair[0]))

    groups: dict[str, list[str]] = {}
    for word, _count in unlearned:
        mapping = repertoire[word]
        base = mapping.base.lower()
        prerequisite = bool(mapping.slot and base not in learned)
        target = base if prerequisite else word
        groups.setdefault(target, []).append(word)
    recommendations = []
    for target, forms in groups.items():
        prerequisites = any(repertoire[w].slot and repertoire[w].base.lower() == target
                            and target not in learned for w in forms)
        recommendations.append(Recommendation(
            repertoire[target].word,
            tuple(repertoire[w].word for w in sorted(forms)),
            sum(counts[w] for w in forms),
            prerequisites,
        ))
    recommendations.sort(key=lambda r: (-r.tokens, r.word.lower()))

    comparisons = []
    measured_tokens = 0
    legacy_cards = 0
    for word, mapping in repertoire.items():
        entry = progress.get("words", {}).get(mapping.word, {})
        fingerprint = fingerprints[mapping.word]
        if entry and not entry.get("mapping"):
            legacy_cards += 1
        # Unknown/mismatched identities cannot justify measured cost claims.
        if entry.get("mapping") != fingerprint or word not in counts:
            continue
        samples = recall_samples(entry)
        if not samples:
            continue
        measured_tokens += counts[word]
        if baseline_wpm is not None:
            baseline_seconds = (len(mapping.word) + 1) * 60 / (5 * baseline_wpm)
            comparisons.append(RecallComparison(
                mapping.word, counts[word], len(samples), statistics.median(samples), baseline_seconds,
            ))
    comparisons.sort(key=lambda c: (c.estimated_seconds_saved, c.word.lower()))
    return TextAnalysis(
        total_tokens=sum(counts.values()),
        unique_words=len(counts),
        primary_tokens=sum(n for w, n in counts.items() if w in repertoire and repertoire[w].slot == 0),
        alt_tokens=sum(n for w, n in counts.items() if w in repertoire and repertoire[w].slot != 0),
        learned_tokens=sum(n for w, n in counts.items() if w in learned),
        uncovered=uncovered[:limit],
        unlearned=unlearned[:limit],
        recommendations=recommendations[:limit],
        comparisons=comparisons[:limit],
        unmeasured_tokens=sum(n for w, n in counts.items() if w in repertoire) - measured_tokens,
        legacy_cards=legacy_cards,
    )


def format_analysis(report: TextAnalysis) -> str:
    def coverage(count: int) -> str:
        percent = 100 * count / report.total_tokens if report.total_tokens else 0
        return f"{count}/{report.total_tokens} ({percent:.1f}%)"

    lines = [
        f"Word tokens: {report.total_tokens}; unique words: {report.unique_words}",
        f"Assigned coverage: {coverage(report.primary_tokens + report.alt_tokens)}",
        f"  Primary: {report.primary_tokens}; alt: {report.alt_tokens}",
        f"Independently learned coverage: {coverage(report.learned_tokens)}",
        "Coverage uses normalized words; punctuation/non-word tokens are not measured.",
        "CSV availability is not a firmware deployment check.",
    ]
    if report.legacy_cards:
        lines.append(f"Legacy mapping identity unknown for {report.legacy_cards} cards; mastery is provisional.")
    for title, values in (("Frequent uncovered words", report.uncovered),
                          ("Available but unlearned", report.unlearned)):
        lines.append(f"\n{title}:")
        lines.extend(f"  {word}: {count}" for word, count in values)
        if not values:
            lines.append("  None")
    lines.append("\nNext to learn (potential token coverage, not measured speed benefit):")
    for suggestion in report.recommendations:
        prerequisite = "base first, then listed forms" if suggestion.prerequisite else "independent form"
        lines.append(f"  {suggestion.word}: {suggestion.tokens} tokens [{prerequisite}]; "
                     + ", ".join(suggestion.forms))
    if not report.recommendations:
        lines.append("  None")
    lines.append(f"\nAssigned tokens without current unassisted recall data: {report.unmeasured_tokens}")
    if report.comparisons:
        lines.append("Recall vs supplied baseline (estimates; input method is not detected):")
        for c in report.comparisons:
            label = "slower than baseline" if c.estimated_seconds_saved < 0 else "potential saving"
            lines.append(f"  {c.word}: recall {c.recall_seconds:.2f}s (n={c.samples}), "
                         f"baseline {c.baseline_seconds:.2f}s; "
                         f"{c.estimated_seconds_saved:+.2f}s over {c.tokens} tokens ({label})")
    else:
        lines.append("Speed comparison needs --baseline-wpm and current unassisted recall observations.")
    return "\n".join(lines)


@dataclass(frozen=True)
class DifficultForm:
    mapping: PracticeMapping
    lapses: int
    reps: int
    samples: int
    recall_seconds: float | None
    leech: bool


@dataclass
class DifficultyAnalysis:
    forms: list[DifficultForm]
    identities: Counter[str]
    invalid: dict[str, str]

    @property
    def most_lapses(self) -> list[DifficultForm]:
        return sorted((form for form in self.forms if form.lapses > 0),
                      key=lambda form: (-form.lapses, form.mapping.word.lower(), form.mapping.word))

    @property
    def longest_recalls(self) -> list[DifficultForm]:
        return sorted((form for form in self.forms if form.samples >= RECALL_MIN_SAMPLES),
                      key=lambda form: (-(form.recall_seconds or 0), form.mapping.word.lower(), form.mapping.word))


def analyze_difficulty(
    chords: list[Chord],
    progress: dict | None,
    *,
    keyboard_kind: str,
    keyboard_layout: list[list[str]],
    leech_threshold: int = 8,
) -> DifficultyAnalysis:
    """Describe evidence for verified current mappings, without changing cards."""
    if not keyboard_layout or not any(key.strip("_ ") for row in keyboard_layout for key in row):
        raise ValueError("Identity comparison unavailable: keyboard layout is empty.")
    if any(not isinstance(row.get("word"), str) or not row["word"].strip()
           or any(char.isspace() for char in row["word"]) for row in chords):
        raise ValueError("Identity comparison unavailable: invalid dictionary word cells; run chordgen check.")
    repertoire = build_repertoire(chords)
    fingerprints = mapping_fingerprints(repertoire, keyboard_kind, keyboard_layout)
    mappings = {mapping.word: mapping for mapping in repertoire.values()}
    words = (progress or {}).get("words", {})
    if not isinstance(words, dict):
        raise ValueError("Progress words must be a mapping.")
    forms = []
    identities = Counter()
    invalid = {}
    for word, entry in words.items():
        error = progress_entry_error(entry)
        if error is not None:
            invalid[word] = error
            identities["invalid"] += 1
        elif word not in fingerprints:
            identities["unavailable"] += 1
        elif not entry.get("mapping"):
            identities["unknown"] += 1
        elif entry["mapping"] != fingerprints[word]:
            identities["changed"] += 1
        else:
            identities["current"] += 1
            samples = recall_samples(entry)
            lapses = entry.get("lapses", 0)
            forms.append(DifficultForm(
                mappings[word], lapses, entry.get("reps", 0), len(samples),
                statistics.median(samples) if samples else None,
                leech_threshold > 0 and lapses >= leech_threshold,
            ))
    return DifficultyAnalysis(forms, identities, invalid)


def format_difficulty(report: DifficultyAnalysis, limit: int = 10) -> str:
    if limit < 1:
        raise ValueError("limit must be positive")

    def timing(form: DifficultForm) -> str:
        if form.recall_seconds is None:
            return "recall unmeasured (n=0)"
        return f"median recall {form.recall_seconds:.2f}s (n={form.samples})"

    lines = [
        "Difficult chords: current-mapping evidence",
        "Progress: " + ", ".join(f"{report.identities[key]} {label}" for key, label in (
            ("current", "current"), ("unknown", "unknown identity"), ("changed", "changed"),
            ("unavailable", "unavailable"), ("invalid", "invalid"),
        )),
        "Only verified current cards contribute below; other identities are excluded.",
        "Verified means saved mapping identity matches, not dictionary or firmware validation; run chordgen check.",
    ]
    if report.invalid:
        lines.append("Partial report: malformed cards excluded; run chordgen check for details.")
        for word in sorted(report.invalid)[:limit]:
            lines.append(f"  {word!r}: {report.invalid[word]}")
        if len(report.invalid) > limit:
            lines.append(f"  ... {len(report.invalid) - limit} more invalid cards")
    if not report.forms:
        lines.append("No verified current learning evidence yet.")
    for title, forms, empty in (
        ("Most lapses", report.most_lapses, "No recorded lapses on verified current mappings."),
        (f"Longest unassisted recalls (at least {RECALL_MIN_SAMPLES} samples)", report.longest_recalls,
         "Not enough unassisted recall samples; use chordgen learn --recall."),
    ):
        lines.append(f"\n{title}: {len(forms)} forms")
        for form in forms[:limit]:
            mapping = form.mapping
            slot = f"alt{mapping.slot}" if mapping.slot else "primary"
            label = " [leech]" if form.leech else ""
            lines.append(f"  {mapping.word!r}: {mapping.hint!r}; base {mapping.base!r}, {slot}; "
                         f"{form.lapses} lapses, {form.reps} reviews{label}; {timing(form)}; "
                         f"{len(mapping.word)} characters")
        if not forms:
            lines.append(f"  {empty}")
        if len(forms) > limit:
            lines.append(f"  ... {len(forms) - limit} more ({len(forms)} total)")
    insufficient = sum(form.samples < RECALL_MIN_SAMPLES for form in report.forms)
    lines.append(f"\nCurrent forms below {RECALL_MIN_SAMPLES} recall samples: {insufficient}/{len(report.forms)}")
    lines.append("By practice slot (all verified current cards, before display limits):")
    for slot in range(4):
        forms = [form for form in report.forms if form.mapping.slot == slot]
        name = f"alt{slot}" if slot else "primary"
        lines.append(f"  {name}: {len(forms)} current cards; "
                     f"{sum(form.lapses > 0 for form in forms)}/{len(forms)} with lapses; "
                     f"{sum(form.lapses for form in forms)} total lapses; "
                     f"{sum(form.samples >= RECALL_MIN_SAMPLES for form in forms)}/{len(forms)} recall-ranked")
    lines.extend([
        "\nLapses are lifetime Again ratings on graduated cards, not all errors or a recent failure rate.",
        "Slot counts reflect practice ownership and unequal exposure, not modifier failure rates.",
        "Recall medians use clean, hint-free learn --recall attempts (up to 200 stored per form).",
        "Three samples is a display minimum, not statistical confidence; samples have no timestamps.",
        "Seconds include word length, thinking and the committing space; typing vs chords is not detected.",
        "Longest does not mean physically bad. This ranking is separate from learn's WPM grading.",
        "\nPractice: chordgen learn --recall; target forms with chordgen drill WORD ... (no FSRS updates).",
        "Inspect: chordgen check. Only repin manually in chords.csv after checking the mapping and comfort.",
        "Read-only: no files changed, mappings reassigned, or progress reset.",
    ])
    return "\n".join(lines)
