"""Personal-text reports are local, deterministic, and read-only."""

from copy import deepcopy
import json

from fsrs import Rating
import pytest
from typer.testing import CliRunner

from chordgen import book as book_module, cli, srs
from chordgen.analysis import analyze_text, format_analysis
from chordgen.book import load_book
from chordgen.chord import build_repertoire, mapping_fingerprints


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    text = tmp_path / "text.txt"
    text.write_text("Look, looks LOOKS looked unknown unknown! 123 --")
    chords = [
        {"word": "look", "chord": "lk", "frequency": "", "alt1": "looks", "alt2": "looked"},
        {"word": "looks", "chord": "", "frequency": "5"},
    ]
    return text, chords, srs.load_progress()


def test_counts_and_family_recommendations_are_unique_and_read_only(corpus):
    text, chords, progress = corpus
    original = deepcopy((chords, progress))
    report = analyze_text(load_book(text), chords, progress)
    assert report.total_tokens == 6
    assert report.unique_words == 4
    assert (report.primary_tokens, report.alt_tokens, report.learned_tokens) == (1, 3, 0)
    assert report.uncovered == [("unknown", 2)]
    assert len(report.recommendations) == 1
    recommendation = report.recommendations[0]
    assert recommendation.word == "look"
    assert recommendation.tokens == 4
    assert recommendation.prerequisite
    assert set(recommendation.forms) == {"look", "looks", "looked"}
    assert (chords, progress) == original
    assert "4/6 (66.7%)" in format_analysis(report)


def test_base_mastery_does_not_inflate_alt_coverage(corpus):
    text, chords, progress = corpus
    srs.record_review(progress, srs.make_scheduler(learning_steps=1), "look", Rating.Good, None)
    report = analyze_text(load_book(text), chords, progress)
    assert report.learned_tokens == 1
    assert report.legacy_cards == 1
    assert [(r.word, r.tokens, r.prerequisite) for r in report.recommendations] == [
        ("looks", 2, False), ("looked", 1, False),
    ]


def test_primary_and_competing_alt_owners_do_not_double_count(corpus):
    text, chords, progress = corpus
    chords.append({"word": "rival", "chord": "rv", "alt1": "looks"})
    chords.append({"word": "looks", "chord": "ls"})
    report = analyze_text(load_book(text), chords, progress)
    assert report.primary_tokens == 3
    assert report.alt_tokens == 1
    assert sum(r.tokens for r in report.recommendations) == 4


def test_current_unassisted_recall_is_required_for_speed_estimates(corpus):
    text, chords, progress = corpus
    fingerprints = mapping_fingerprints(build_repertoire(chords), "standard", None)
    scheduler = srs.make_scheduler(learning_steps=1)
    srs.record_review(progress, scheduler, "looks", Rating.Good, 12.0,
                      speed_mode="recall", elapsed_seconds=5.0,
                      fingerprint=fingerprints["looks"])
    # An unknown legacy identity cannot justify a measured timing claim.
    srs.record_review(progress, scheduler, "look", Rating.Good, 60.0,
                      speed_mode="recall", elapsed_seconds=1.0)
    report = analyze_text(load_book(text), chords, progress, baseline_wpm=60)
    assert report.learned_tokens == 3
    assert report.unmeasured_tokens == 2
    assert len(report.comparisons) == 1
    comparison = report.comparisons[0]
    assert comparison.word == "looks"
    assert comparison.baseline_seconds == pytest.approx(1.2)
    assert comparison.estimated_seconds_saved == pytest.approx(-7.6)
    assert "slower than baseline" in format_analysis(report)
    changed_layout = analyze_text(load_book(text), chords, progress, keyboard_layout=[["x"]], baseline_wpm=60)
    assert changed_layout.comparisons == []
    assert changed_layout.learned_tokens == 1


@pytest.mark.parametrize("baseline", [0, -1, float("nan"), float("inf")])
def test_invalid_baselines_are_rejected(corpus, baseline):
    text, chords, progress = corpus
    with pytest.raises(ValueError, match="finite and positive"):
        analyze_text(load_book(text), chords, progress, baseline_wpm=baseline)


def test_empty_text_has_zero_coverage_without_division_by_zero(corpus):
    text, chords, progress = corpus
    text.write_text("123 -- !!!")
    report = analyze_text(load_book(text), chords, progress)
    assert report.total_tokens == 0
    assert report.recommendations == []
    assert "0/0 (0.0%)" in format_analysis(report)


def test_epub_reuses_book_parser(tmp_path):
    from ebooklib import epub
    book = epub.EpubBook()
    book.set_identifier("test")
    book.set_title("Practice")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Words", file_name="words.xhtml", lang="en")
    chapter.content = "<h1>Look</h1><p>looks looks</p>"
    book.add_item(chapter)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [chapter]
    path = tmp_path / "practice.epub"
    epub.write_epub(str(path), book)
    report = analyze_text(load_book(path), [{"word": "look", "chord": "lk", "alt1": "looks"}], {"words": {}})
    # The shared loader includes navigation text as well as chapter text.
    assert report.total_tokens == 4
    assert report.uncovered == [("practice", 1)]
    assert report.alt_tokens == 2


def test_limits_do_not_change_coverage_or_family_totals(corpus):
    text, chords, progress = corpus
    text.write_text("looks looks rival missing unknown")
    chords.append({"word": "rival", "chord": "rv", "alt1": "looks"})
    report = analyze_text(load_book(text), chords, progress, limit=1)
    assert report.total_tokens == 5
    assert report.primary_tokens + report.alt_tokens == 3
    assert report.uncovered == [("missing", 1)]
    assert report.unlearned == [("looks", 2)]
    assert len(report.recommendations) == 1
    recommendation = report.recommendations[0]
    assert (recommendation.word, recommendation.tokens) == ("look", 2)
    assert recommendation.forms == ("looks",)
    assert recommendation.prerequisite
    unlimited = analyze_text(load_book(text), chords, progress)
    assert sum(r.tokens for r in unlimited.recommendations) == 3
    with pytest.raises(ValueError, match="limit must be positive"):
        analyze_text(load_book(text), chords, progress, limit=0)


def test_recall_uses_finite_positive_median_and_counts_samples(corpus):
    text, chords, progress = corpus
    fingerprint = mapping_fingerprints(build_repertoire(chords), "standard", None)["looks"]
    srs.record_review(progress, srs.make_scheduler(learning_steps=1), "looks", Rating.Good,
                      60, fingerprint=fingerprint)
    progress["words"]["looks"]["recall_seconds"] = [
        0.5, 0.1, 0.3, 0, -1, float("nan"), float("inf"), "2", None, True, False,
    ]
    before = deepcopy(progress)
    report = analyze_text(load_book(text), chords, progress, baseline_wpm=60)
    comparison = report.comparisons[0]
    assert comparison.samples == 3
    assert comparison.recall_seconds == pytest.approx(0.3)
    assert comparison.estimated_seconds_saved == pytest.approx(1.8)
    assert "potential saving" in format_analysis(report)
    assert progress == before
    without_baseline = analyze_text(load_book(text), chords, progress)
    assert without_baseline.comparisons == []
    assert without_baseline.unmeasured_tokens == 2


@pytest.mark.parametrize("progress_version", [3, 4, 99, None])
def test_analyze_cli_preserves_all_input_files(tmp_path, monkeypatch, progress_version):
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    if progress_version is not None:
        srs.PROGRESS_FILE.write_text(json.dumps({"version": progress_version, "words": {}, "speed_samples": [999]}))
    chords = tmp_path / "chords.csv"
    chords.write_text("word,chord,frequency,alt1\nlook,lk,,looks\n")
    config = tmp_path / "config.yaml"
    config.write_text(f"gen:\n  file: {chords}\n")
    text = tmp_path / "text.md"
    text.write_text("look looks looks")
    monkeypatch.setattr(book_module, "BOOKS_FILE", tmp_path / "books.json")
    book_module.BOOKS_FILE.write_text('{"books": {"existing": {"token_index": 42}}}')
    files = [config, chords, text, book_module.BOOKS_FILE]
    if progress_version is not None:
        files.append(srs.PROGRESS_FILE)
    originals = [p.read_bytes() for p in files]
    original_paths = set(tmp_path.iterdir())
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-c", str(config), "analyze", str(text), "--baseline-wpm", "60"])
    assert result.exit_code == 0, result.output
    assert "Assigned coverage: 3/3 (100.0%)" in result.output
    assert "Speed comparison needs" in result.output
    assert [p.read_bytes() for p in files] == originals
    assert set(tmp_path.iterdir()) == original_paths
    invalid = runner.invoke(cli.app, ["-c", str(config), "analyze", str(text), "--limit", "0"])
    assert invalid.exit_code != 0
    unsupported = tmp_path / "text.pdf"
    unsupported.write_text("not a PDF")
    error = runner.invoke(cli.app, ["-c", str(config), "analyze", str(unsupported)])
    assert error.exit_code != 0
    assert "Unsupported book format" in error.output
