"""Tests for chordgen.utils.find_combinations.

``find_combinations`` is the prefix-lock generator behind the scorer:
every combination it returns must start with the word's first
character, and results are ordered shortest-first.
"""

from __future__ import annotations

from chordgen.utils import find_combinations


def test_every_combination_starts_with_first_character():
    combos = find_combinations("the")
    assert combos, "expected at least one combination"
    assert all(c.startswith("t") for c in combos)


def test_excludes_empty_string():
    assert "" not in find_combinations("the")


def test_enumerates_all_prefix_locked_subsequences():
    # For ``abc`` the subsequences that keep ``a`` first, preserving
    # left-to-right order, are: abc, ab, ac, a.
    assert set(find_combinations("abc")) == {"abc", "ab", "ac", "a"}


def test_results_ordered_longest_first():
    # The recursion emits the fully-included combination first and the
    # bare prefix last (longest -> shortest).
    combos = find_combinations("abc")
    assert combos[0] == "abc"
    assert combos[-1] == "a"
    lengths = [len(c) for c in combos]
    assert lengths == sorted(lengths, reverse=True)


def test_single_character_returns_itself():
    assert find_combinations("a") == ["a"]
