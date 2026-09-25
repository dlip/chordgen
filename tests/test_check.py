"""Health checks must diagnose inputs without changing user-owned state."""

from copy import deepcopy
import csv
import json
import os
import subprocess
import sys

from fsrs import Card, State
import pytest
from typer.testing import CliRunner
import yaml

from chordgen import cli, srs
from chordgen.check import CSV_FIELDS, check_dictionary, format_check, run_check
from chordgen.chord import build_repertoire, mapping_fingerprints
from chordgen.config import Config
from chordgen.keyboard_view import resolve_keyboard_layout
from chordgen.output import assigned_rows


def test_cli_disables_textual_smooth_scroll_by_default():
    env = os.environ.copy()
    env.pop("TEXTUAL_SMOOTH_SCROLL", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import chordgen.cli; "
            "from textual.constants import SMOOTH_SCROLL; "
            "print(SMOOTH_SCROLL)",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.stdout.strip() == "False"


def row(word="the", chord="te", **fields):
    return dict.fromkeys(CSV_FIELDS, "") | {"word": word, "chord": chord} | fields


def config_for(*formats):
    return Config.model_validate({"output": {"formats": list(formats), "qmk": {"key_codes": {}}}})


def codes(report):
    return {finding.code for finding in report.findings}


def examples(report, code):
    return next(f.examples for f in report.findings if f.code == code)


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    config = config_for("qmk")
    config.gen.file = tmp_path / "chords.csv"
    config.output.qmk.file = tmp_path / "output.def"
    config.output.qmk.file.write_text("existing output")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()))
    with config.gen.file.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(row(alt1="thes"))
    (tmp_path / "books.json").write_text('{"books": {"sample": {"token_index": 4}}}')
    return path, config


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


def test_healthy_dictionary_is_read_only_with_pins_and_irregular_alts():
    config = config_for("qmk")
    rows = [row("I", "i", alt1="me"), row("be", "b", alt1="is"),
            row("is", ""), row("n't", "nt", category="contraction")]
    original = deepcopy((config, rows))
    report = check_dictionary(config, rows)
    assert not report.has_errors
    assert not any(f.severity == "warning" for f in report.findings)
    assert any("4/4 practice mappings selected" in line for line in report.summary)
    assert (config, rows) == original


def test_duplicate_words_physical_chords_and_repeated_keys():
    report = check_dictionary(config_for(), [row("The", "te"), row("the", "et"), row("bad", "bb")])
    assert {"word.duplicate", "chord.duplicate", "chord.repeated-key"} <= codes(report)
    assert report.has_errors
    assert "record 2" in examples(report, "word.duplicate")[0]


def test_active_alts_have_explicit_precedence_and_dormant_ones_do_not_warn():
    rows = [row("look", "lk", alt1="looks", alt2="looks", alt3="look"),
            row("rival", "rv", alt1="looks"), row("looks", "ls"),
            row("dormant", "", alt1="looks"), row("n't", "nt", category="contraction", alt1="looks")]
    report = check_dictionary(config_for(), rows)
    assert {"alt.shared", "alt.shadowed", "alt.self"} <= codes(report)
    text = format_check(report)
    assert "practice uses 'looks' (ls)" in text
    assert "dormant" not in text
    assert "record 6" not in text


def test_multiword_alts_are_valid_but_edge_whitespace_warns():
    config = config_for("qmk")
    valid = check_dictionary(config, [row("happy", "hp", alt1="more happy")])
    assert "alt.whitespace" not in codes(valid)
    assert not valid.has_errors
    padded = check_dictionary(config, [row("happy", "hp", alt1=" more happy ")])
    assert "alt.whitespace" in codes(padded)
    assert "export.qmk.coverage" in codes(padded)


def test_missing_keys_are_not_replaced_again():
    config = config_for()
    config.gen.key_replacement = {"?": "x"}
    report = check_dictionary(config, [row("what", "?"), row("bad", "_")])
    assert {"chord.missing-key", "chord.placeholder"} <= codes(report)


@pytest.mark.parametrize("layout", [["a"], ["a" * 13] * 3, [], ["_qwertyuiop_", "_asdfghjkl;_", "_zxcvbnm,./", "____"]])
def test_malformed_geometry_is_a_diagnostic_not_a_crash(layout):
    config = config_for()
    config.gen.keyboard.standard.layout = "custom"
    config.gen.keyboard.standard.custom_layout = layout
    report = check_dictionary(config, [row()])
    assert "layout.shape" in codes(report)


def test_duplicate_layout_labels_ignore_placeholders():
    config = config_for()
    assert "layout.duplicate" not in codes(check_dictionary(config, [row()]))
    config.gen.keyboard.standard.layout = "custom"
    config.gen.keyboard.standard.custom_layout[0] = "_qqertyuiop_"
    report = check_dictionary(config, [row()])
    assert "layout.duplicate" in codes(report)


def test_short_effort_map_does_not_crash():
    config = config_for()
    config.gen.keyboard.standard.effort_map = ["1"]
    assert "layout.shape" in codes(check_dictionary(config, [row()]))


def test_standard_comfort_is_informational_unless_constraints_reject():
    report = check_dictionary(config_for(), [row("pair", "qa"), row("long", "wert"), row("scissor", "tz")])
    assert {"comfort.same-finger", "comfort.long", "comfort.scissor"} <= codes(report)
    assert not report.has_errors
    config = config_for()
    config.gen.keyboard.standard.same_column_chord_penalty = -1
    constrained = check_dictionary(config, [row("pair", "qa")])
    assert "chord.constraints" in codes(constrained)
    assert not constrained.has_errors


def test_directional_same_finger_and_missing_keys():
    config = config_for()
    config.gen.keyboard.type = "directional"
    report = check_dictionary(config, [row("pair", "io"), row("unknown", "!")])
    assert "chord.missing-key" in codes(report)
    assert "comfort.same-finger" in codes(report)
    assert "chord.constraints" in codes(report)


def test_progress_known_changed_legacy_missing_and_invalid():
    config = config_for()
    rows = [row("same", "sa"), row("changed", "ch"), row("legacy", "lg")]
    fingerprints = mapping_fingerprints(build_repertoire(rows), *resolve_keyboard_layout(config))
    card = Card(state=State.Review).to_dict()
    progress = {"version": 4, "words": {
        "same": {"card": card, "mapping": fingerprints["same"]},
        "changed": {"card": card, "mapping": "old"},
        "legacy": {"card": card}, "removed": {"card": card}, "broken": {"card": {}},
    }}
    original = deepcopy(progress)
    report = check_dictionary(config, rows, progress)
    assert {"progress.changed", "progress.legacy", "progress.unavailable", "progress.card"} <= codes(report)
    assert "1 matching, 1 unknown identity, 1 changed, 1 unavailable" in "\n".join(report.summary)
    assert progress == original


@pytest.mark.parametrize("version", [2, 3, 4])
def test_legacy_progress_is_not_migrated_on_disk(files, version):
    path, _ = files
    srs.PROGRESS_FILE.write_text(json.dumps({"version": version, "words": {"the": {"card": Card().to_dict()}}}))
    before = snapshot(path.parent)
    assert "progress.legacy" in codes(run_check(path))
    assert snapshot(path.parent) == before


@pytest.mark.parametrize("payload,code", [("bad json", "progress.invalid"), ('{"version":99}', "progress.version"),
                                           ('{"version":4,"words":[]}', "progress.invalid")])
def test_invalid_progress_is_not_silently_ignored(files, payload, code):
    path, _ = files
    srs.PROGRESS_FILE.write_text(payload)
    before = snapshot(path.parent)
    report = run_check(path)
    assert code in codes(report)
    assert report.has_errors
    assert snapshot(path.parent) == before


def test_export_limits_count_assigned_rows_including_contractions():
    rows = [row("skip", ""), row("n't", "nt", category="contraction"), row("look", "lk", alt1="looks")]
    assert assigned_rows(rows, 1) == [rows[1]]
    assert assigned_rows(rows, 0) == rows[1:]
    assert assigned_rows(rows, -1) == []
    config = config_for("kanata", "zmk")
    config.output.kanata.key_mapping = {key: key for key in "ntlk"}
    config.output.kanata.limit = config.output.zmk.limit = 1
    report = check_dictionary(config, rows)
    assert {"export.kanata.omitted", "export.zmk.omitted", "export.kanata.coverage", "export.zmk.coverage"} <= codes(report)
    assert sum("0/2 practice mappings selected" in line for line in report.summary) == 2


def test_export_coverage_matches_mapping_not_just_word():
    config = config_for("zmk")
    config.output.zmk.limit = 1
    rows = [row("look", "lk", alt1="looks"), row("looks", "ls")]
    report = check_dictionary(config, rows)
    assert "'looks': 'looks' (ls), slot 0" in examples(report, "export.zmk.coverage")
    assert any("1/2 practice mappings selected" in line for line in report.summary)


def test_primary_only_and_training_remainder():
    config = config_for("charachorder", "training")
    rows = [row(f"word{i}", key) for i, key in enumerate("abcdefghijk")]
    rows[0]["alt1"] = "extra"
    report = check_dictionary(config, rows)
    assert {"export.charachorder.primary-only", "export.training.primary-only", "export.training.omitted"} <= codes(report)
    assert any("Export charachorder: 11/12" in line for line in report.summary)
    assert any("Export training: 10/12" in line for line in report.summary)
    assert "export.charachorder.coverage" not in codes(report)
    assert len(examples(report, "export.training.coverage")) == 1


@pytest.mark.parametrize("name", ["qmk", "kanata", "zmk"])
def test_translation_errors_block_target(name):
    config = config_for(name)
    report = check_dictionary(config, [row("symbol", "?")])
    assert f"export.{name}.translation" in codes(report)
    assert any(f"Export {name}: BLOCKED;" in line for line in report.summary)


def test_resolved_key_and_modifier_collisions():
    config = config_for("kanata")
    config.output.kanata.key_mapping = {"a": "x", "b": "x"}
    report = check_dictionary(config, [row("one", "a"), row("two", "b")])
    assert "export.kanata.collision" in codes(report)
    repeated = check_dictionary(config, [row("pair", "ab")])
    assert "export.kanata.binding" in codes(repeated)
    config.output.kanata.alt1_keys = []
    alt = check_dictionary(config, [row("one", "a", alt1="ones")])
    assert "export.kanata.collision" in codes(alt)


def test_zmk_punctuation_collision_and_missing_trigger():
    config = config_for("zmk")
    report = check_dictionary(config, [row("semi", ";")])
    assert "export.zmk.collision" in codes(report)
    config.output.zmk.chord_keys = ["missing"]
    report = check_dictionary(config, [])
    assert "export.zmk.translation" in codes(report)


def test_disabled_exporters_are_not_checked():
    report = check_dictionary(config_for(), [row()])
    assert "export.none" in codes(report)
    assert not any(code.startswith("export.kanata") for code in codes(report))


def test_cli_never_calls_writers_or_creates_files(files, monkeypatch):
    path, _ = files
    def forbidden(*args, **kwargs):
        pytest.fail("check attempted to write or generate")
    monkeypatch.setattr(cli, "load_or_create_config", forbidden)
    monkeypatch.setattr(cli, "write_chords", forbidden)
    monkeypatch.setattr(cli, "save_progress", forbidden)
    from chordgen.output.qmk import QmkOutput
    monkeypatch.setattr(QmkOutput, "output", forbidden)
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "check"])
    assert result.exit_code == 0, result.output
    assert "progress.absent" in result.output
    assert "no files changed" in result.output
    assert snapshot(path.parent) == before
    missing = path.parent / "new-directory" / "config.yaml"
    result = CliRunner().invoke(cli.app, ["-c", str(missing), "check"])
    assert result.exit_code == 1
    assert "config.invalid" in result.output
    assert snapshot(path.parent) == before


def test_cli_warnings_succeed_errors_fail_and_limit_only_changes_display(files):
    path, config = files
    with config.gen.file.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(row("look", "lk", alt1="look"))
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-c", str(path), "check"])
    assert result.exit_code == 0, result.output
    assert "alt.self" in result.output
    with config.gen.file.open("a") as stream:
        stream.write("bad,qq,,,,,\nworse,aa,,,,,\n")
    before = snapshot(path.parent)
    short = runner.invoke(cli.app, ["-c", str(path), "check", "--limit", "1"])
    long = runner.invoke(cli.app, ["-c", str(path), "check", "--limit", "100"])
    assert short.exit_code == long.exit_code == 1
    assert "1 more (2 total)" in short.output
    assert snapshot(path.parent) == before
    assert runner.invoke(cli.app, ["-c", str(path), "check", "--limit", "0"]).exit_code == 2


@pytest.mark.parametrize("text,code", [
    ("word,chord\nthe,te\n", "csv.headers"),
    ("word,chord,category,frequency,alt1,alt2,alt3,word\n", "csv.headers"),
    (",".join(CSV_FIELDS) + "\nthe,te\n", "csv.row"),
    (",".join(CSV_FIELDS) + '\n"unclosed', "csv.invalid"),
    (",".join(CSV_FIELDS) + "\n,te,,,,,\n", "word.invalid"),
])
def test_malformed_csv_is_read_only_and_diagnostic(files, text, code):
    path, config = files
    config.gen.file.write_text(text)
    before = snapshot(path.parent)
    report = run_check(path)
    assert code in codes(report)
    assert report.has_errors
    assert snapshot(path.parent) == before


def test_extra_named_csv_columns_are_allowed(files):
    path, config = files
    config.gen.file.write_text(",".join(CSV_FIELDS) + ",debug\nthe,te,,,,,,notes\n")
    assert not run_check(path).has_errors


@pytest.mark.parametrize("text", ["[]", "false", "gen: [", "gen:\n  file: null\n"])
def test_malformed_config_does_not_create_defaults(files, text):
    path, _ = files
    path.write_text(text)
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "check"])
    assert result.exit_code == 1, result.output
    assert "config.invalid" in result.output
    assert snapshot(path.parent) == before


def test_missing_csv_does_not_get_created(files):
    path, config = files
    config.gen.file.unlink()
    before = snapshot(path.parent)
    report = run_check(path)
    assert "csv.invalid" in codes(report)
    assert snapshot(path.parent) == before


def test_legacy_config_is_interpreted_in_memory_only(files):
    path, _ = files
    path.write_text(path.read_text() + "train:\n  learning_steps: 2\n")
    # Remove the learn block without changing other config sections.
    raw = yaml.safe_load(path.read_text())
    raw.pop("learn")
    path.write_text(yaml.safe_dump(raw))
    before = snapshot(path.parent)
    report = run_check(path)
    assert "config.legacy" in codes(report)
    assert snapshot(path.parent) == before


def test_progress_bad_auxiliary_state_is_reported(files):
    path, _ = files
    srs.PROGRESS_FILE.write_text(json.dumps({"version": 4, "daily": [], "speed_samples": "bad", "words": {
        "the": {"card": Card().to_dict(), "reps": "bad"},
    }}))
    report = run_check(path)
    assert {"progress.daily", "progress.samples", "progress.card"} <= codes(report)


def test_formatter_is_deterministic_and_limits_all_examples():
    report = check_dictionary(config_for(), [row("one", "aaaa"), row("two", "bbbb")])
    assert format_check(report, 1) == format_check(report, 1)
    assert "1 more (2 total)" in format_check(report, 1)
    with pytest.raises(ValueError):
        format_check(report, 0)


def test_all_output_selections_agree_with_actual_files(tmp_path):
    config = config_for("qmk", "zmk", "kanata", "charachorder", "training")
    rows = [row(f"word{i}", key, alt1=f"form{i}") for i, key in enumerate("abcdefghijk")]
    config.output.qmk.file = tmp_path / "qmk.def"
    config.output.kanata.file = tmp_path / "kanata.kbd"
    config.output.kanata.key_mapping = {key: key for key in "abcdefghijk"}
    config.output.zmk.chords_file = tmp_path / "chords.dtsi"
    config.output.zmk.macros_file = tmp_path / "macros.dtsi"
    config.output.charachorder.file = tmp_path / "cc.json"
    config.output.training.file = tmp_path / "training.txt"
    config.output.zmk.limit = config.output.kanata.limit = 2
    report = check_dictionary(config, rows)
    assert not report.has_errors
    for name in config.output.formats:
        getattr(config.output, name).output(rows)
    qmk = config.output.qmk.file.read_text()
    kanata = config.output.kanata.file.read_text()
    zmk = config.output.zmk.chords_file.read_text()
    cc = json.loads(config.output.charachorder.file.read_text())
    training = config.output.training.file.read_text()
    assert qmk.count("SUBS(") == 44
    assert kanata.count("(macro ") == 8
    # Three convenience punctuation chords, plus normal/shifted primary/alts.
    assert zmk.count("CHORD(") - 1 == 11
    assert len(cc["chords"]) == 11
    assert "word9" in training and "word10" not in training
    for name, count in (("qmk", 22), ("zmk", 4), ("kanata", 4), ("charachorder", 11), ("training", 10)):
        assert any(f"Export {name}: {count}/22" in line for line in report.summary)
