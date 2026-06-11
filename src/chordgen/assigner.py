"""Chord assignment: pick a chord per word from per-word scored options.

Runs after Scorer has populated `options` for each row. Reduces the
problem to a sparse minimum-weight bipartite matching:

  Left vertices  : words needing a chord (the pool below)
  Right vertices : distinct sorted-chord keys across all candidates,
                   plus one slack vertex per word.
  Edge weight    : option.score * weight(word)
  Slack edge     : unmatched_penalty * weight(word) — taken iff no
                   real edge yields a cheaper assignment.

Solved exactly via scipy.sparse.csgraph.min_weight_full_bipartite_matching
(LAPJVsp). For ~2000 words and ~60k edges this runs in well under a
second and produces a globally cost-optimal assignment, replacing the
old greedy + 2-swap + eviction phases.

Cost model: cost(option, word) = option.score * weight(word), where weight
is the parsed `frequency` column floored at min_frequency_weight and
raised to `frequency_exponent` (default 3.0). Higher weight = paying score
hurts more, so frequent words attract low-score chords. An exponent > 1
sharpens that preference and discourages the matcher from trading a
common word's short chord to a rarer competitor.

When `assignment.priority_tiers` is non-empty, the pool is split into
successive tiers by frequency rank and each tier is solved by the same
matcher in order, with previous tiers' chord keys reserved out. This
protects frequent words from being out-bid by the long tail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import min_weight_full_bipartite_matching

from chordgen.alt_generator import is_base_form
from chordgen.chord import Chord, Option
from chordgen.config import GenOptions


@dataclass
class AssignmentReport:
    no_options: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    cost: float = 0.0


def _parse_freq(chord: Chord, floor: float) -> float:
    raw = chord.get("frequency", "")
    if not raw:
        return floor
    try:
        return max(float(raw), floor)
    except (TypeError, ValueError):
        return floor


def _sorted_key(chord_str: str) -> str:
    return "".join(sorted(chord_str))


def _viable_options(chord: Chord, min_chord_length: int) -> list[Option]:
    """Per-word options filtered by min_chord_length, sorted by score asc."""
    opts = chord.get("options") or []
    return [o for o in opts if len(o["chord"]) >= min_chord_length]


def _is_reserved(chord: Chord) -> bool:
    """A row is user-reserved if it has a chord pinned by hand.

    Setup writes `frequency` for every generated row; a hand-edited row
    won't have it. So `chord` set with empty `frequency` is the signal
    that the user wants this chord pinned.
    """
    return bool(chord.get("chord")) and not chord.get("frequency")


def _passes_min_word_length(chord: Chord, min_word_length: int) -> bool:
    """Mirror the scorer's min_word_length rule (scorer.py).

    Contractions are exempt — they're short by construction and the
    user explicitly imported them.
    """
    if chord.get("category", "") == "contraction":
        return True
    return len(chord["word"]) >= min_word_length


def _split_into_tiers(
    pool: list[Chord], cutoffs: list[int]
) -> list[tuple[int, int]]:
    """Return [(start, end), ...] slice bounds for each successive tier.

    Empty `cutoffs` returns a single (0, len(pool)) tier (single global
    pass). Cutoffs are clamped to len(pool); empty tiers are skipped by
    the caller.
    """
    if not cutoffs:
        return [(0, len(pool))]
    bounds = [0] + [min(c, len(pool)) for c in cutoffs] + [len(pool)]
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]


def _solve_pool(
    pool: list[Chord],
    viables: list[list[Option]],
    weights: list[float],
    start: int,
    end: int,
    reserved_keys: set[str],
    options: GenOptions,
    report: AssignmentReport,
    holder_by_key: dict[str, str],
    tier_label: str,
) -> None:
    """Build + solve the matching for pool[start:end], applying picks in place.

    `reserved_keys` is mutated: every chord key picked in this tier is
    added to it so subsequent tiers won't reuse it.
    `holder_by_key` is also mutated for diagnostics continuity.
    """
    cfg = options.assignment

    n_rows = end - start
    if n_rows == 0:
        return

    # Re-filter each row's viables against the *current* reserved_keys
    # (later tiers see earlier tiers' claims, plus user pins).
    tier_viables: list[list[Option]] = []
    for i in range(start, end):
        v = [o for o in viables[i] if _sorted_key(o["chord"]) not in reserved_keys]
        tier_viables.append(v)

    # Map each distinct viable sorted-key to a column index.
    key_to_col: dict[str, int] = {}
    for v in tier_viables:
        for opt in v:
            key = _sorted_key(opt["chord"])
            if key not in key_to_col:
                key_to_col[key] = len(key_to_col)
    n_chord_cols = len(key_to_col)
    n_cols = n_chord_cols + n_rows  # + per-row slack columns

    # Build COO arrays.
    # scipy's matcher requires a 0-cost edge to be representable; it
    # treats *missing* entries as +inf and *explicit zeros* as zero cost.
    # We'll add a tiny epsilon so genuine zero scores stay distinguishable
    # from missing edges.
    eps = 1e-9
    row_idx: list[int] = []
    col_idx: list[int] = []
    data: list[float] = []
    edge_option: dict[tuple[int, int], Option] = {}

    for r, v in enumerate(tier_viables):
        w = weights[start + r]
        # Real chord edges. If the same sorted-key appears more than once
        # for a single word (different orderings score the same key),
        # keep the cheaper.
        best_for_col: dict[int, Option] = {}
        for opt in v:
            c = key_to_col[_sorted_key(opt["chord"])]
            prev = best_for_col.get(c)
            if prev is None or opt["score"] < prev["score"]:
                best_for_col[c] = opt
        for c, opt in best_for_col.items():
            row_idx.append(r)
            col_idx.append(c)
            cost = opt["score"] * w + eps
            data.append(cost)
            edge_option[(r, c)] = opt
        # Slack edge for this row.
        slack_col = n_chord_cols + r
        row_idx.append(r)
        col_idx.append(slack_col)
        data.append(cfg.unmatched_penalty * w + eps)

    biadjacency = csr_matrix(
        (np.asarray(data, dtype=np.float64), (row_idx, col_idx)),
        shape=(n_rows, n_cols),
    )

    matched_rows, matched_cols = min_weight_full_bipartite_matching(biadjacency)

    matched_count = 0
    unmatched_count = 0
    tier_cost = 0.0
    for r, c in zip(matched_rows, matched_cols):
        chord = pool[start + r]
        if c >= n_chord_cols:
            report.no_options.append(chord["word"].lower())
            unmatched_count += 1
            continue
        opt = edge_option[(r, c)]
        chord["chord"] = opt["chord"]
        key = _sorted_key(opt["chord"])
        tier_cost += opt["score"] * weights[start + r]
        holder_by_key[key] = chord["word"].lower()
        reserved_keys.add(key)
        matched_count += 1

    report.cost += tier_cost
    print(
        f"{tier_label}: {matched_count} matched, {unmatched_count} unmatched, "
        f"cost={tier_cost:.1f}"
    )


def assign_chords(chords: list[Chord], options: GenOptions) -> AssignmentReport:
    report = AssignmentReport()
    cfg = options.assignment
    floor = cfg.min_frequency_weight

    # ---- Phase A: reserved chords ----------------------------------------
    # User-pinned rows are removed from the optimisation entirely; their
    # chord-keys are reserved so no other word can match them.
    reserved_keys: set[str] = set()
    for chord in chords:
        if not _is_reserved(chord):
            # Clear any chord left over from a previous gen run so the
            # row is eligible for reassignment.
            chord["chord"] = ""
            continue
        key = _sorted_key(chord["chord"])
        if key in reserved_keys:
            raise Exception(
                f"Reserved chord for word {chord['word']} already pinned "
                f"by another row"
            )
        reserved_keys.add(key)

    # ---- Build pool of words eligible for assignment ---------------------
    # Words reachable as another row's alt (e.g. "made" as the past form
    # of "make") shouldn't get a primary chord — they'd shadow nothing
    # useful and waste contention. Coverage is contributed only by
    # *base/root* rows (verbs in lemma form, nominative pronouns,
    # ``this``, cardinal numbers, present-tense modals, ...). This
    # guarantees that the canonical base of a paradigm survives even
    # when the inflected sibling has higher SUBTLEX frequency: e.g.
    # ``your`` doesn't cover ``you``, and ``that`` doesn't cover
    # ``this``. Open-class categories (verb / noun / adjective / adverb)
    # treat every row as a base, preserving the historical behaviour
    # there.
    coverable: set[str] = set()
    for chord in chords:
        word = chord["word"].lower()
        if not _passes_min_word_length(chord, options.min_word_length):
            continue
        if not is_base_form(chord["word"], chord.get("category", "")):
            continue
        for slot in ("alt1", "alt2", "alt3"):
            alt = (chord.get(slot) or "").strip().lower()
            if alt and alt != word:
                coverable.add(alt)

    seen_words: set[str] = set()
    pool: list[Chord] = []
    skipped_alt_covered: list[str] = []
    for chord in chords:
        word = chord["word"].lower()
        if word in seen_words:
            report.duplicate.append(word)
            continue
        seen_words.add(word)
        if not _passes_min_word_length(chord, options.min_word_length):
            continue
        if _is_reserved(chord):
            continue
        if word in coverable:
            chord["alt1"] = ""
            chord["alt2"] = ""
            chord["alt3"] = ""
            skipped_alt_covered.append(word)
            continue
        pool.append(chord)

    if not pool:
        _print_diagnostics(report, skipped_alt_covered, [], [], {})
        return report

    # ---- Build per-row viables / weights once over the full pool --------
    # Reserved-key filtering happens per-tier inside _solve_pool, so we
    # don't apply it here.
    weights: list[float] = []
    viables: list[list[Option]] = []
    exponent = cfg.frequency_exponent
    for chord in pool:
        v = _viable_options(chord, options.min_chord_length)
        viables.append(v)
        weights.append(_parse_freq(chord, floor) ** exponent)

    # ---- Solve each tier in turn ----------------------------------------
    holder_by_key: dict[str, str] = {}
    tier_bounds = _split_into_tiers(pool, list(cfg.priority_tiers))
    n_tiers = len(tier_bounds)
    for i, (start, end) in enumerate(tier_bounds):
        if start == end:
            continue
        tier_label = f"Tier {i + 1}/{n_tiers} (n={end - start})"
        _solve_pool(
            pool,
            viables,
            weights,
            start,
            end,
            reserved_keys,
            options,
            report,
            holder_by_key,
            tier_label,
        )

    _print_diagnostics(report, skipped_alt_covered, pool, viables, holder_by_key)
    return report


def _print_diagnostics(
    report: AssignmentReport,
    skipped_alt_covered: list[str],
    pool: list[Chord],
    viables: list[list[Option]],
    holder_by_key: dict[str, str],
) -> None:
    if report.no_options:
        word_to_idx = {c["word"].lower(): i for i, c in enumerate(pool)}
        print(f"Unable to find any options for {len(report.no_options)} words:")
        for word in report.no_options:
            i = word_to_idx.get(word)
            if i is None:
                print(f"  {word}: (no candidates)")
                continue
            tops = viables[i][:3]
            if not tops:
                print(f"  {word}: (no candidates)")
                continue
            holders = []
            for opt in tops:
                key = _sorted_key(opt["chord"])
                h = holder_by_key.get(key)
                holders.append(
                    f"{opt['chord']} -> {h}" if h else f"{opt['chord']} (free?)"
                )
            print(f"  {word}: blocked by [{', '.join(holders)}]")
    if report.duplicate:
        print(
            f"Ignored {len(report.duplicate)} duplicate words: "
            f"{', '.join(report.duplicate)}"
        )
    if skipped_alt_covered:
        print(
            f"Skipped {len(skipped_alt_covered)} words already reachable as "
            f"alts of other rows: {', '.join(skipped_alt_covered)}"
        )
    print(f"Cost: {report.cost:.1f}")
    logging.debug(
        "Assignment done: %d unmatched, %d duplicates",
        len(report.no_options),
        len(report.duplicate),
    )
