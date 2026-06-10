"""Tests for the drill word-pool selection and learned-word
highlight set. Drill defaults to the FSRS-graduated pool; passing
a custom word list widens the pool to every word in the list with
a chord assigned, with graduated words flagged for highlighting."""

from __future__ import annotations

from fsrs import Card, State

from chordgen.config import Config
from chordgen.drill import DrillApp


def _new_drill(chords, progress) -> DrillApp:
    """Construct a DrillApp without invoking Textual's App machinery.
    We bypass ``__init__`` entirely and only set the attributes the
    pool / highlight helpers touch.
    """

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.config = Config().drill
    app.custom_words = None
    app.learned_words = app._collect_learned_words(progress)
    app.word_pool = sorted(app.learned_words)
    return app


def _progress_with(words: dict[str, State]) -> dict:
    """Build a minimal ``progress.json``-shaped dict where each
    listed word has a Card serialised in the requested state."""

    out = {"words": {}}
    for word, state in words.items():
        card = Card()
        card.state = state
        out["words"][word] = {"card": card.to_dict()}
    return out


def test_collect_learned_words_intersects_review_state_with_chords_map():
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "and", "chord": "an"},
        {"word": "of", "chord": "of"},
    ]
    progress = _progress_with(
        {
            "the": State.Review,
            "and": State.Learning,
            "of": State.Review,
            # ``ghost`` is in progress but missing from chords.csv —
            # it must be ignored.
            "ghost": State.Review,
        }
    )

    app = _new_drill(chords, progress)

    assert app.learned_words == {"the", "of"}


def test_default_pool_is_graduated_only():
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "and", "chord": "an"},
        {"word": "of", "chord": "of"},
    ]
    progress = _progress_with(
        {
            "the": State.Review,
            "and": State.Learning,
        }
    )

    app = _new_drill(chords, progress)

    # Only ``the`` has graduated, so the default pool is just that.
    # ``and`` (Learning) and ``of`` (no progress entry) are excluded.
    assert app.word_pool == ["the"]


def test_custom_word_pool_includes_unlearned_words_with_chords():
    chords = [
        {"word": "the", "chord": "te"},
        {"word": "and", "chord": "an"},
        {"word": "of", "chord": "of"},
    ]
    progress = _progress_with({"the": State.Review})

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.config = Config().drill
    app.custom_words = ["the", "and", "of", "missing"]
    app.learned_words = app._collect_learned_words(progress)
    app.word_pool = app._filter_custom_words(app.custom_words)

    # Pool keeps every chordable word from the supplied list,
    # regardless of FSRS state, but drops ``missing`` (no chord).
    assert app.word_pool == ["the", "and", "of"]
    # Highlight set still reflects FSRS state.
    assert app.learned_words == {"the"}


def test_filter_custom_words_drops_words_without_chord():
    chords = [{"word": "the", "chord": "te"}]
    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}

    assert app._filter_custom_words(["the", "missing", "alsogone"]) == [
        "the"
    ]
