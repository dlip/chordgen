"""Tests for the gen pipeline's ignore-words handling."""

from chordgen.gen import _merge_ignored, _split_ignored


def test_split_ignored_separates_case_insensitively():
    chords = [
        {"word": "ho"},
        {"word": "Oi"},
        {"word": "dog"},
        {"word": "Cat"},
    ]
    active, ignored = _split_ignored(chords, ["ho", "oi"])
    assert [c["word"] for c in active] == ["dog", "Cat"]
    assert [(i, c["word"]) for i, c in ignored] == [(0, "ho"), (1, "Oi")]


def test_split_ignored_passes_through_when_empty():
    chords = [{"word": "ho"}, {"word": "dog"}]
    active, ignored = _split_ignored(chords, [])
    assert active is chords
    assert ignored == []


def test_merge_ignored_preserves_order_and_clears_chord_alts():
    active = [
        {"word": "dog", "chord": "dg", "alt1": "", "alt2": "", "alt3": ""},
    ]
    ignored = [
        (0, {"word": "ho", "chord": "h", "alt1": "", "alt2": "", "alt3": "", "debug": "x"}),
        (2, {"word": "oi", "chord": "oi", "alt1": "", "alt2": "", "alt3": ""}),
    ]
    merged = _merge_ignored(active, ignored)
    assert [c["word"] for c in merged] == ["ho", "dog", "oi"]
    assert merged[0]["chord"] == ""
    assert merged[0]["alt1"] == ""
    assert merged[0].get("debug") == ""
    assert merged[2]["chord"] == ""


def _generation_fixture(tmp_path, monkeypatch):
    import csv
    from concurrent.futures import ThreadPoolExecutor
    from chordgen import gen, srs
    from chordgen.config import GenOptions
    from fsrs import Rating

    monkeypatch.setattr(gen, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    path = tmp_path / "chords.csv"
    rows = [
        {"word": "hello", "chord": "hl", "frequency": "6", "category": "", "alt1": "hellos", "alt2": "", "alt3": ""},
        {"word": "world", "chord": "wd", "frequency": "", "category": "", "alt1": "", "alt2": "", "alt3": ""},
    ]
    with path.open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    options = GenOptions(file=path)
    progress = srs.load_progress()
    srs.record_review(progress, srs.make_scheduler(learning_steps=1), "hello", Rating.Good, None)
    srs.save_progress(progress)
    return options, progress


def test_generate_preview_is_read_only_and_flags_learned(tmp_path, monkeypatch):
    from copy import deepcopy
    from chordgen import gen, srs
    options, progress = _generation_fixture(tmp_path, monkeypatch)
    before = options.file.read_bytes()
    prior_progress = deepcopy(progress)
    before_progress = srs.PROGRESS_FILE.read_bytes()
    result = gen.generate(options, progress=progress)
    assert result.learned_changes == ["hello"]
    assert result.changes
    assert options.file.read_bytes() == before
    assert srs.PROGRESS_FILE.read_bytes() == before_progress
    assert progress == prior_progress
    assert "hello" not in result.progress["words"]


def test_preserve_learned_retains_frequency_alts_and_manual_pins(tmp_path, monkeypatch):
    from chordgen import gen
    options, progress = _generation_fixture(tmp_path, monkeypatch)
    options.alts.overwrite = True
    result = gen.generate(options, progress=progress, preserve_learned=True)
    hello, world = result.chords
    assert hello["chord"] == "hl"
    assert hello["frequency"] == "6"
    assert hello["alt1"] == "hellos"
    assert world["chord"] == "wd"
    assert result.learned_changes == []
    assert result.progress["words"]["hello"]["mapping"]


def test_preserve_rejects_ignored_learned_word(tmp_path, monkeypatch):
    import pytest
    from chordgen import gen
    options, progress = _generation_fixture(tmp_path, monkeypatch)
    options.ignore_words = ["HELLO"]
    before = options.file.read_bytes()
    with pytest.raises(ValueError, match="ignored learned"):
        gen.generate(options, progress=progress, preserve_learned=True)
    assert options.file.read_bytes() == before


def test_gen_cli_dry_run_abort_and_accept(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from chordgen import cli, srs
    options, _progress = _generation_fixture(tmp_path, monkeypatch)
    config = tmp_path / "config.yaml"
    config.write_text(f"gen:\n  file: {options.file}\n")
    before = options.file.read_bytes()
    before_config = config.read_bytes()
    before_progress = srs.PROGRESS_FILE.read_bytes()
    runner = CliRunner()
    dry = runner.invoke(cli.app, ["-c", str(config), "gen", "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "Learned mappings changing: hello" in dry.output
    assert "no files written" in dry.output
    assert options.file.read_bytes() == before
    assert config.read_bytes() == before_config
    assert srs.PROGRESS_FILE.read_bytes() == before_progress
    abort = runner.invoke(cli.app, ["-c", str(config), "gen"], input="n\n")
    assert abort.exit_code != 0
    assert options.file.read_bytes() == before
    assert srs.PROGRESS_FILE.read_bytes() == before_progress
    accept = runner.invoke(cli.app, ["-c", str(config), "gen", "--yes"])
    assert accept.exit_code == 0, accept.output
    assert options.file.read_bytes() != before
    assert "hello" not in srs.load_progress()["words"]
