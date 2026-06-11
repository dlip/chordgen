"""Tests for the drill word-pool selection and learned-word
highlight set. Drill defaults to the FSRS-graduated pool; passing
a custom word list widens the pool to every word in the list with
a chord assigned, with graduated words flagged for highlighting."""

from __future__ import annotations

from fsrs import Card, State

from chordgen.config import Config
from chordgen.chord import build_alt_index
from chordgen.drill import DrillApp


def _new_drill(chords, progress) -> DrillApp:
    """Construct a DrillApp without invoking Textual's App machinery.
    We bypass ``__init__`` entirely and only set the attributes the
    pool / highlight helpers touch.
    """

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.alt_index = build_alt_index(chords)
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
    app.alt_index = build_alt_index(chords)
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
    app.alt_index = build_alt_index(chords)

    assert app._filter_custom_words(["the", "missing", "alsogone"]) == [
        "the"
    ]


def test_collect_learned_words_includes_alts_of_graduated_base():
    chords = [
        {
            "word": "car",
            "chord": "ca",
            "alt1": "cars",
            "alt2": "carred",
            "alt3": "",
        },
        {
            "word": "the",
            "chord": "te",
            "alt1": "thes",
            "alt2": "",
            "alt3": "",
        },
    ]
    # ``car`` is graduated, ``the`` is still in Learning.
    progress = _progress_with(
        {"car": State.Review, "the": State.Learning}
    )

    app = _new_drill(chords, progress)

    # Base + its alts ride along; the unrelated row's alts don't.
    assert app.learned_words == {"car", "cars", "carred"}


def test_chord_for_word_returns_slot_suffixed_chord_for_alt():
    chords = [
        {
            "word": "set",
            "chord": "au",
            "alt1": "sets",
            "alt2": "setting",
            "alt3": "settings",
        },
    ]
    progress = _progress_with({"set": State.Review})
    app = _new_drill(chords, progress)
    app.current_word_had_error = True

    # Base word: chord without suffix.
    assert app._chord_for_word("set", is_current=True) == "au"
    # Alts: chord + slot digit.
    assert app._chord_for_word("sets", is_current=True) == "au1"
    assert app._chord_for_word("setting", is_current=True) == "au2"
    assert app._chord_for_word("settings", is_current=True) == "au3"
    # Hidden until the user stumbles on the current word.
    app.current_word_had_error = False
    assert app._chord_for_word("sets", is_current=True) == ""


def test_drill_include_alts_false_excludes_alt_forms():
    chords = [
        {
            "word": "car",
            "chord": "ca",
            "alt1": "cars",
            "alt2": "",
            "alt3": "",
        },
    ]
    progress = _progress_with({"car": State.Review})

    # Build a DrillApp with the knob disabled — alt_index should be
    # empty and ``cars`` should not appear in the learned set or
    # produce a slot-suffixed chord.
    cfg = Config().drill
    cfg.include_alts = False

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.alt_index = (
        build_alt_index(chords) if cfg.include_alts else {}
    )
    app.config = cfg
    app.custom_words = None
    app.learned_words = app._collect_learned_words(progress)

    assert app.alt_index == {}
    assert app.learned_words == {"car"}
    # Custom-word filter also drops alts when the knob is off.
    assert app._filter_custom_words(["car", "cars"]) == ["car"]


def test_drill_always_show_chords_reveals_chord_without_stumble():
    chords = [
        {"word": "car", "chord": "ca", "alt1": "cars", "alt2": "", "alt3": ""},
    ]
    progress = _progress_with({"car": State.Review})

    cfg = Config().drill
    cfg.always_show_chords = True

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.alt_index = build_alt_index(chords)
    app.config = cfg
    app.custom_words = None
    app.learned_words = app._collect_learned_words(progress)
    app.current_word_had_error = False

    # No stumble required: chord is shown for current and trailing words.
    assert app._chord_for_word("car", is_current=True) == "ca"
    assert app._chord_for_word("car", is_current=False) == "ca"
    assert app._chord_for_word("cars", is_current=False) == "ca1"


def test_drill_always_show_chords_default_off_keeps_stumble_gating():
    chords = [{"word": "car", "chord": "ca"}]
    progress = _progress_with({"car": State.Review})

    cfg = Config().drill  # always_show_chords defaults to False

    app = DrillApp.__new__(DrillApp)
    app.chords_map = {c["word"]: c for c in chords if c["chord"]}
    app.alt_index = build_alt_index(chords)
    app.config = cfg
    app.custom_words = None
    app.learned_words = app._collect_learned_words(progress)
    app.current_word_had_error = False

    # Default: hidden until stumble.
    assert app._chord_for_word("car", is_current=True) == ""
    app.current_word_had_error = True
    assert app._chord_for_word("car", is_current=True) == "ca"
    # Trailing words stay hidden even on a stumble.
    assert app._chord_for_word("car", is_current=False) == ""
