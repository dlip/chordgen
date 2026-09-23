"""Read-only personal-text coverage and practice recommendations."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import statistics

from chordgen.book import Book
from chordgen.chord import Chord, build_repertoire, mapping_fingerprints
from chordgen.srs import ProgressFile, learned_words


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
        samples = [float(t) for t in entry.get("recall_seconds", [])
                   if isinstance(t, (int, float)) and math.isfinite(t) and t > 0]
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
