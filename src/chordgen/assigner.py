"""Chord assignment: pick a chord per word from per-word scored options.

Pipeline (called by gen.py after Scorer has populated `options` per row):

  Phase A — Reserved chords:    apply user-pinned reserved_chord values.
  Phase B — Greedy:              frequency-weighted greedy assignment with
                                 contention-aware tie-breaking.
  Phase C — 2-swap local search: pairwise swap until no improvement.
  Phase D — Eviction recovery:   try to fill no_options words by single-step
                                 eviction of an assigned word.
  Phase E — Diagnostics:         report holders of each unfilled word's top
                                 candidates so collisions are debuggable.

Cost model: cost(option, word) = option.score * weight(word), where weight
is the parsed `frequency` column floored at min_frequency_weight. Higher
weight = paying score hurts more, so frequent words attract low-score
chords.
"""

from __future__ import annotations

import logging
import random
from collections import Counter
from dataclasses import dataclass, field

from chordgen.chord import Chord, Option
from chordgen.config import GenOptions


@dataclass
class AssignmentReport:
    no_options: list[str] = field(default_factory=list)
    duplicate: list[str] = field(default_factory=list)
    evicted: list[tuple[str, str]] = field(default_factory=list)
    cost_after_greedy: float = 0.0
    cost_after_swap: float = 0.0
    cost_after_eviction: float = 0.0


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


def assign_chords(chords: list[Chord], options: GenOptions) -> AssignmentReport:
    report = AssignmentReport()
    cfg = options.assignment
    floor = cfg.min_frequency_weight

    # ---- Phase A: reserved chords ----------------------------------------
    used: dict[str, Chord] = {}  # sorted_chord -> chord row holding it
    for chord in chords:
        reserved = chord.get("reserved_chord") or ""
        if not reserved:
            continue
        chord["chord"] = reserved
        sorted_key = _sorted_key(reserved)
        if sorted_key in used:
            raise Exception(
                f"Reserved chord for word {chord['word']} already used "
                f"for {used[sorted_key]['word']}"
            )
        used[sorted_key] = chord

    # ---- Build pool of words eligible for greedy assignment --------------
    # Words already reachable as an earlier row's alt (e.g. "made" as the
    # past form of "make") shouldn't get a primary chord — they'd shadow
    # nothing useful and waste contention. Walk rows in CSV (frequency)
    # order: a row is kept if it's not already covered by an earlier-kept
    # row's alts. This naturally breaks cycles (e.g. could→can, can→could)
    # by keeping the higher-frequency one.
    coverable: set[str] = set()  # words reachable as alt of an earlier kept row
    seen_words: set[str] = set()
    pool: list[Chord] = []  # rows we still need to assign
    skipped_alt_covered: list[str] = []
    for chord in chords:
        word = chord["word"].lower()
        if word in seen_words:
            report.duplicate.append(word)
            continue
        seen_words.add(word)
        if len(word) < options.min_word_length:
            continue
        if chord.get("reserved_chord"):
            # Reserved row keeps its chord; its alts still cover other words.
            for slot in ("alt1", "alt2", "alt3"):
                alt = (chord.get(slot) or "").strip().lower()
                if alt and alt != word:
                    coverable.add(alt)
            continue
        if word in coverable:
            # Already reachable via an earlier row's chord+alt-key; don't
            # waste a primary chord on it. Clear its own alt slots too —
            # those would be inflections of an inflection.
            chord["alt1"] = ""
            chord["alt2"] = ""
            chord["alt3"] = ""
            skipped_alt_covered.append(word)
            continue
        # Keeping this row: register its alts as covering future words.
        for slot in ("alt1", "alt2", "alt3"):
            alt = (chord.get(slot) or "").strip().lower()
            if alt and alt != word:
                coverable.add(alt)
        pool.append(chord)

    # Precompute viable options per row and per-row weight.
    viable: dict[int, list[Option]] = {}
    weight: dict[int, float] = {}
    top_k_keys: dict[int, list[str]] = {}
    for chord in pool:
        cid = id(chord)
        v = _viable_options(chord, options.min_chord_length)
        viable[cid] = v
        weight[cid] = _parse_freq(chord, floor)
        top_k_keys[cid] = [_sorted_key(o["chord"]) for o in v[: cfg.top_k]]

    # Contention counter: how many words have each chord-key in their top-K?
    contention: Counter[str] = Counter()
    for keys in top_k_keys.values():
        contention.update(set(keys))

    # ---- Phase B: frequency-weighted greedy ------------------------------
    # Iterate pool in CSV order (already frequency-sorted). For each word,
    # pick the lowest score among free options; break ties by lowest
    # contention.
    placed: dict[int, Option] = {}  # cid -> Option
    for chord in pool:
        cid = id(chord)
        v = viable[cid]
        best: Option | None = None
        best_key: tuple[int, int] | None = None  # (score, contention_count)
        for opt in v:
            key = _sorted_key(opt["chord"])
            if key in used:
                continue
            tie = (opt["score"], contention[key])
            if best is None or tie < best_key:  # type: ignore[operator]
                best = opt
                best_key = tie
        if best is None:
            report.no_options.append(chord["word"].lower())
            continue
        chord["chord"] = best["chord"]
        used[_sorted_key(best["chord"])] = chord
        placed[cid] = best

    def total_cost() -> float:
        c = 0.0
        for cid, opt in placed.items():
            c += opt["score"] * weight[cid]
        return c

    report.cost_after_greedy = total_cost()

    # ---- Phase C: 2-swap local search ------------------------------------
    # Only consider candidate pairs (a, b) where each has the other's
    # current chord in its top-K options. That's where a swap is feasible.
    cid_to_row = {id(c): c for c in pool}
    if cfg.max_swap_passes > 0 and placed:
        # Index assigned chord-keys -> cid for fast lookup.
        key_to_cid: dict[str, int] = {
            _sorted_key(opt["chord"]): cid for cid, opt in placed.items()
        }
        # For each placed cid, options indexed by sorted_key for fast scoring.
        opts_by_key: dict[int, dict[str, Option]] = {
            cid: {_sorted_key(o["chord"]): o for o in viable[cid]}
            for cid in placed
        }

        for _ in range(cfg.max_swap_passes):
            pairs: list[tuple[int, int]] = []
            for cid_a in placed:
                # Look at cid_a's top-K candidates: any of those keys
                # currently held by some cid_b is a swap candidate.
                for opt_alt in viable[cid_a][: cfg.top_k]:
                    key = _sorted_key(opt_alt["chord"])
                    cid_b = key_to_cid.get(key)
                    if cid_b is None or cid_b == cid_a:
                        continue
                    pairs.append((cid_a, cid_b))
            random.shuffle(pairs)

            improved_any = False
            for cid_a, cid_b in pairs:
                # Rows may have been swapped already this pass; re-check.
                opt_a = placed[cid_a]
                opt_b = placed[cid_b]
                key_a = _sorted_key(opt_a["chord"])
                key_b = _sorted_key(opt_b["chord"])
                # Do A and B each have the other's chord scored?
                a_takes_b = opts_by_key[cid_a].get(key_b)
                b_takes_a = opts_by_key[cid_b].get(key_a)
                if a_takes_b is None or b_takes_a is None:
                    continue
                w_a = weight[cid_a]
                w_b = weight[cid_b]
                current = opt_a["score"] * w_a + opt_b["score"] * w_b
                proposed = a_takes_b["score"] * w_a + b_takes_a["score"] * w_b
                if proposed < current:
                    placed[cid_a] = a_takes_b
                    placed[cid_b] = b_takes_a
                    cid_to_row[cid_a]["chord"] = a_takes_b["chord"]
                    cid_to_row[cid_b]["chord"] = b_takes_a["chord"]
                    # update key->cid map
                    key_to_cid.pop(key_a, None)
                    key_to_cid.pop(key_b, None)
                    key_to_cid[_sorted_key(a_takes_b["chord"])] = cid_a
                    key_to_cid[_sorted_key(b_takes_a["chord"])] = cid_b
                    improved_any = True
            if not improved_any:
                break

        # Rebuild `used` so the eviction phase below sees a consistent view.
        used = {}
        for chord in chords:
            reserved = chord.get("reserved_chord") or ""
            if reserved:
                used[_sorted_key(reserved)] = chord
        for cid, opt in placed.items():
            used[_sorted_key(opt["chord"])] = cid_to_row[cid]

    report.cost_after_swap = total_cost()

    # ---- Phase D: eviction recovery --------------------------------------
    # For each no_options word, try to evict one assigned word that holds a
    # chord this word needs, where the evicted word can still be reassigned
    # to a free option AND the total cost decreases.
    if report.no_options:
        word_to_chord: dict[str, Chord] = {c["word"].lower(): c for c in pool}
        recovered: list[str] = []

        for word in report.no_options:
            requester = word_to_chord.get(word)
            if requester is None:
                continue
            cid_r = id(requester)
            w_r = weight[cid_r]
            best_eviction: tuple[float, Option, int, Option] | None = None

            for opt_r in viable[cid_r]:
                key = _sorted_key(opt_r["chord"])
                # The chord must currently be held by an assigned word
                # (not by a reserved one; we don't evict user pins).
                holder = used.get(key)
                if holder is None:
                    continue
                if holder.get("reserved_chord"):
                    continue
                cid_h = id(holder)
                if cid_h not in placed:
                    continue
                opt_h_now = placed[cid_h]
                # Find a free fallback for the holder.
                fallback: Option | None = None
                for opt_alt in viable[cid_h]:
                    alt_key = _sorted_key(opt_alt["chord"])
                    if alt_key == key:
                        continue
                    if alt_key in used:
                        continue
                    fallback = opt_alt
                    break
                if fallback is None:
                    continue
                w_h = weight[cid_h]
                # Net cost change of the eviction: requester contributes
                # opt_r*w_r (was 0) and holder swings opt_h_now*w_h -> fallback*w_h.
                delta = (
                    opt_r["score"] * w_r
                    + fallback["score"] * w_h
                    - opt_h_now["score"] * w_h
                )
                # Pick the eviction with the smallest delta. We recover the
                # word even when delta > 0 (an unfilled word is worse than a
                # small cost increase), but prefer cheaper recoveries.
                if best_eviction is None or delta < best_eviction[0]:
                    best_eviction = (delta, opt_r, cid_h, fallback)

            if best_eviction is None:
                continue

            delta, opt_r, cid_h, fallback = best_eviction
            holder = cid_to_row[cid_h]
            old_holder_opt = placed[cid_h]
            # Apply eviction.
            requester["chord"] = opt_r["chord"]
            holder["chord"] = fallback["chord"]
            placed[cid_r] = opt_r
            placed[cid_h] = fallback
            used.pop(_sorted_key(old_holder_opt["chord"]), None)
            used[_sorted_key(opt_r["chord"])] = requester
            used[_sorted_key(fallback["chord"])] = holder
            report.evicted.append((word, holder["word"].lower()))
            recovered.append(word)

        # Drop recovered words from no_options.
        report.no_options = [w for w in report.no_options if w not in set(recovered)]

    report.cost_after_eviction = total_cost()

    # ---- Phase E: diagnostics --------------------------------------------
    if report.no_options:
        word_to_chord = {c["word"].lower(): c for c in pool}
        print(f"Unable to find any options for {len(report.no_options)} words:")
        for word in report.no_options:
            requester = word_to_chord.get(word)
            if requester is None:
                continue
            top = viable[id(requester)][:3]
            holders = []
            for opt in top:
                key = _sorted_key(opt["chord"])
                holder = used.get(key)
                if holder is None:
                    holders.append(f"{opt['chord']} (free?)")
                else:
                    holders.append(f"{opt['chord']} -> {holder['word']}")
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

    if report.evicted:
        print(f"Recovered {len(report.evicted)} words via eviction:")
        for word, by in report.evicted:
            print(f"  {word} (evicted {by})")

    print(
        f"Cost: greedy={report.cost_after_greedy:.1f} "
        f"swap={report.cost_after_swap:.1f} "
        f"eviction={report.cost_after_eviction:.1f}"
    )

    logging.debug(
        "Assignment done: %d placed, %d no_options, %d duplicates, %d evicted",
        len(placed),
        len(report.no_options),
        len(report.duplicate),
        len(report.evicted),
    )

    return report
