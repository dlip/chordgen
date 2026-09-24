"""Difficulty reports attribute evidence without changing learning state."""

from copy import deepcopy
import csv
import json

from fsrs import Card, State
import pytest
from typer.testing import CliRunner
import yaml

from chordgen import cli, srs
from chordgen.analysis import analyze_difficulty, format_difficulty
from chordgen.check import CSV_FIELDS
from chordgen.chord import build_repertoire, mapping_fingerprints
from chordgen.config import Config
from chordgen.keyboard_view import resolve_keyboard_layout


def row(word="look", chord="lk", **fields):
    return dict.fromkeys(CSV_FIELDS, "") | {"word": word, "chord": chord} | fields


def entry(mapping=None, lapses=0, reps=10, samples=()):
    value = {"card": Card(state=State.Review).to_dict(), "lapses": lapses,
             "reps": reps, "recall_seconds": list(samples)}
    if mapping is not None:
        value["mapping"] = mapping
    return value


def progress_for(rows, **values):
    fingerprints = mapping_fingerprints(build_repertoire(rows), *resolve_keyboard_layout(Config()))
    return {"version": 4, "words": {
        word: entry(fingerprint, **values.get(word, {})) for word, fingerprint in fingerprints.items()
    }}


def analyze(rows, progress, **kwargs):
    kind, layout = resolve_keyboard_layout(Config())
    return analyze_difficulty(rows, progress, keyboard_kind=kind, keyboard_layout=layout, **kwargs)


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob("*")}


def test_lapse_and_recall_rankings_are_separate_deterministic_and_read_only():
    rows = [row("zeta", "zt"), row("Beta", "bt"), row("alpha", "al")]
    progress = progress_for(rows, zeta={"lapses": 9, "samples": [1, 2, 3]},
                            Beta={"lapses": 2, "samples": [6, 4, 5]},
                            alpha={"lapses": 2, "samples": [5, 5, 5]})
    original = deepcopy((rows, progress))
    report = analyze(rows, progress)
    assert [f.mapping.word for f in report.most_lapses] == ["zeta", "alpha", "Beta"]
    assert [f.mapping.word for f in report.longest_recalls] == ["alpha", "Beta", "zeta"]
    assert report.most_lapses[0].leech
    assert report.most_lapses[0].recall_seconds == 2
    assert (rows, progress) == original
    text = format_difficulty(report, 1)
    assert text.count("2 more (3 total)") == 2
    assert "13 total lapses" in text
    assert "Verified means saved mapping identity matches, not dictionary or firmware validation" in text
    assert "3/3 recall-ranked" in text
    assert text == format_difficulty(analyze(rows, {"words": dict(reversed(list(progress["words"].items())))}), 1)
    with pytest.raises(ValueError, match="limit must be positive"):
        format_difficulty(report, 0)


def test_zero_leech_threshold_disables_labels_not_lapse_list():
    rows = [row()]
    report = analyze(rows, progress_for(rows, look={"lapses": 100}), leech_threshold=0)
    assert len(report.most_lapses) == 1
    assert not report.most_lapses[0].leech
    assert "[leech]" not in format_difficulty(report)


def test_only_finite_positive_numeric_raw_samples_count():
    rows = [row()]
    samples = [1, 3, 2, True, False, "7", None, 0, -1, float("nan"), float("inf"), 10 ** 400]
    progress = progress_for(rows, look={"samples": samples})
    report = analyze(rows, progress)
    assert report.longest_recalls[0].samples == 3
    assert report.longest_recalls[0].recall_seconds == 2
    assert "median recall 2.00s (n=3)" in format_difficulty(report)
    assert progress["words"]["look"]["recall_seconds"] == samples


@pytest.mark.parametrize("samples", [[], [2], [2, 3]])
def test_minimum_recall_samples_and_no_ewma_or_global_fallback(samples):
    rows = [row()]
    progress = progress_for(rows, look={"lapses": 1, "samples": samples})
    progress["speed_samples"] = progress["recall_speed_samples"] = [1] * 30
    progress["words"]["look"].update(wpm_ewma=0.1, recall_wpm_ewma=0.1)
    report = analyze(rows, progress)
    assert not report.longest_recalls
    assert report.most_lapses[0].samples == len(samples)
    assert "Current forms below 3 recall samples: 1/1" in format_difficulty(report)
    assert "chordgen learn --recall" in format_difficulty(report)


def test_mapping_identity_categories_and_native_spelling():
    rows = [row("I", "i"), row("legacy", "lg"), row("changed", "ch"), row("broken", "br"), row("new", "nw")]
    progress = progress_for(rows, I={"lapses": 1})
    progress["words"]["legacy"].pop("mapping")
    progress["words"]["changed"]["mapping"] = "old"
    progress["words"]["broken"]["card"] = {}
    progress["words"].pop("new")
    progress["words"]["removed"] = entry(lapses=99, samples=[99] * 3)
    report = analyze(rows, progress)
    assert report.identities == {"current": 1, "unknown": 1, "changed": 1, "invalid": 1, "unavailable": 1}
    assert [f.mapping.word for f in report.forms] == ["I"]
    assert "Partial report" in format_difficulty(report)
    assert "'I': 'i'; base 'I', primary" in format_difficulty(report)
    changed_rows = deepcopy(rows)
    changed_rows[0]["chord"] = "j"
    assert analyze(changed_rows, progress).identities["changed"] == 2
    kind, layout = resolve_keyboard_layout(Config())
    layout[0][1], layout[0][2] = layout[0][2], layout[0][1]
    changed_layout = analyze_difficulty(rows, progress, keyboard_kind=kind, keyboard_layout=layout)
    assert not changed_layout.forms


def test_slot_totals_are_independent_with_primary_precedence_and_first_alt_owner():
    rows = [row("look", "lk", alt1="looks", alt2="looked", alt3="looking"),
            row("looks", "ls"), row("rival", "rv", alt1="looked"),
            row("I", "i", alt1="me"), row("dormant", "", alt1="ghost"),
            row("n't", "nt", category="contraction", alt1="fake")]
    progress = progress_for(rows, looked={"lapses": 3, "samples": [2] * 3},
                            looking={"lapses": 2}, me={"lapses": 1})
    report = analyze(rows, progress)
    mappings = {form.mapping.word: form.mapping for form in report.forms}
    assert mappings["looks"].slot == 0
    assert mappings["looked"].base == "look"
    assert not {"ghost", "fake", "n't"} & mappings.keys()
    text = format_difficulty(report, 1)
    assert "'looked': 'lk2'; base 'look', alt2" in text
    assert "primary: 4 current cards; 0/4 with lapses; 0 total lapses; 0/4" in text
    assert "alt1: 1 current cards; 1/1 with lapses; 1 total lapses; 0/1" in text
    assert "alt2: 1 current cards; 1/1 with lapses; 3 total lapses; 1/1" in text
    assert "alt3: 1 current cards; 1/1 with lapses; 2 total lapses; 0/1" in text


def test_base_progress_does_not_count_as_alt_evidence_and_multiword_alts_are_literal():
    rows = [row("happy", "hp", alt1="more happy", alt2="[red]happiest")]
    progress = progress_for(rows)
    progress["words"].pop("more happy")
    progress["words"]["[red]happiest"]["lapses"] = 3
    report = analyze(rows, progress)
    assert len(report.forms) == 2
    assert "'[red]happiest'" in format_difficulty(report)
    progress["words"]["more happy"] = entry(mapping_fingerprints(build_repertoire(rows), *resolve_keyboard_layout(Config()))["more happy"], lapses=1)
    assert "'more happy': 'hp1'" in format_difficulty(analyze(rows, progress))
    rows[0]["alt1"], rows[0]["alt2"] = rows[0]["alt2"], rows[0]["alt1"]
    changed = analyze(rows, progress)
    assert changed.identities["changed"] == 2
    assert [form.mapping.word for form in changed.forms] == ["happy"]


@pytest.mark.parametrize("field,value", [("lapses", True), ("lapses", -1), ("reps", "2"),
                                         ("mapping", []), ("recall_seconds", "123"), ("card", {})])
def test_malformed_cards_do_not_hide_valid_cards(field, value):
    rows = [row(), row("good", "gd")]
    progress = progress_for(rows, good={"lapses": 1})
    progress["words"]["look"][field] = value
    report = analyze(rows, progress)
    assert report.identities["invalid"] == 1
    assert [f.mapping.word for f in report.most_lapses] == ["good"]


def test_empty_evidence_and_invalid_input_are_distinct():
    report = analyze([row()], None)
    assert "No verified current learning evidence yet" in format_difficulty(report)
    with pytest.raises(ValueError, match="layout is empty"):
        analyze_difficulty([row()], None, keyboard_kind="standard", keyboard_layout=[])
    with pytest.raises(ValueError, match="word cells"):
        analyze([row("bad word")], None)
    with pytest.raises(ValueError, match="words must be a mapping"):
        analyze([row()], {"words": []})


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    config = Config()
    config.gen.file = tmp_path / "chords.csv"
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config.model_dump()))
    rows = [row(alt1="looks", alt2="looked", alt3="looking")]
    with config.gen.file.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (tmp_path / "books.json").write_text('{"sample": 42}')
    (tmp_path / "output.def").write_text("existing firmware")
    return path, config, rows


@pytest.mark.parametrize("version", [2, 3, 4, None])
def test_cli_is_read_only_with_legacy_and_missing_progress(files, monkeypatch, version):
    path, _, rows = files
    if version is not None:
        progress = progress_for(rows, look={"lapses": 8, "samples": [1, 2, 3]})
        progress["version"] = version
        if version != 4:
            for value in progress["words"].values():
                value.pop("mapping")
        srs.PROGRESS_FILE.write_text(json.dumps(progress))
    def forbidden(*args, **kwargs):
        pytest.fail("read-only command attempted to write or reconcile")
    for module, names in ((cli, ["load_or_create_config", "save_config", "write_chords", "save_progress", "generate"]),
                          (srs, ["save_progress", "record_review", "reconcile_mappings", "load_progress"])):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)
    from chordgen.output.qmk import QmkOutput
    monkeypatch.setattr(QmkOutput, "output", forbidden)
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "difficult"])
    assert result.exit_code == 0, result.output
    assert "no files changed" in result.output
    assert snapshot(path.parent) == before
    if version == 4:
        assert "[leech]" in result.output
    elif version is not None:
        assert "4 unknown identity" in result.output
    else:
        assert "progress.absent" in result.output


@pytest.mark.parametrize("payload", ["{", '{"version":99}', '{"version":4,"words":[]}',
                                     '{"version":4,"daily":[]}', '{"version":4,"speed_samples":"bad"}'])
def test_invalid_progress_does_not_look_like_no_difficulties(files, payload):
    path, _, _ = files
    srs.PROGRESS_FILE.write_text(payload)
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "difficult"])
    assert result.exit_code == 1, result.output
    assert "analysis unavailable" in result.output
    assert "Most lapses" not in result.output
    assert snapshot(path.parent) == before


def test_cli_partial_invalid_cards_and_limit(files):
    path, _, rows = files
    progress = progress_for(rows, look={"lapses": 3}, looks={"lapses": 2}, looked={"lapses": 1})
    progress["words"]["looking"]["reps"] = False
    srs.PROGRESS_FILE.write_text(json.dumps(progress))
    before = snapshot(path.parent)
    runner = CliRunner()
    result = runner.invoke(cli.app, ["-c", str(path), "difficult", "--limit", "1"])
    assert result.exit_code == 1, result.output
    assert "Partial report" in result.output
    assert "2 more (3 total)" in result.output
    assert "1 invalid" in result.output
    assert runner.invoke(cli.app, ["-c", str(path), "difficult", "--limit", "0"]).exit_code == 2
    assert snapshot(path.parent) == before


@pytest.mark.parametrize("command", ["difficult", "check"])
def test_missing_csv_parent_is_not_created(files, command):
    path, _, _ = files
    missing = path.parent / "not-created" / "chords.csv"
    path.write_text(f"gen:\n  file: {missing}\n")
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), command])
    assert result.exit_code == 1, result.output
    assert "csv.invalid" in result.output
    assert not missing.parent.exists()
    assert snapshot(path.parent) == before


@pytest.mark.parametrize("kind", ["missing-config", "bad-config", "bad-csv", "bad-word", "missing-csv", "empty-layout", "unresolved-layout"])
def test_cli_bad_inputs_fail_without_writes(files, monkeypatch, kind):
    path, config, _ = files
    if kind == "missing-config":
        path = path.parent / "missing" / "config.yaml"
    elif kind == "bad-config":
        path.write_text("[]")
    elif kind == "bad-csv":
        config.gen.file.write_text("word,chord\nlook,lk\n")
    elif kind == "bad-word":
        config.gen.file.write_text(",".join(CSV_FIELDS) + "\nbad word,lk,,,,,\n")
    elif kind == "missing-csv":
        config.gen.file.unlink()
    elif kind == "empty-layout":
        raw = yaml.safe_load(path.read_text())
        raw["gen"]["keyboard"]["standard"].update(layout="custom", custom_layout=[])
        path.write_text(yaml.safe_dump(raw))
    else:
        monkeypatch.setattr(cli, "resolve_keyboard_layout", lambda _: None)
    before = snapshot(config.gen.file.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "difficult"])
    assert result.exit_code == 1, result.output
    assert "Most lapses" not in result.output
    assert snapshot(config.gen.file.parent) == before


def test_directional_identity_and_legacy_config_are_read_only(files):
    path, config, rows = files
    raw = yaml.safe_load(path.read_text())
    raw["train"] = raw.pop("learn")
    raw["gen"]["keyboard"]["type"] = "directional"
    path.write_text(yaml.safe_dump(raw))
    config.gen.keyboard.type = "directional"
    kind, layout = resolve_keyboard_layout(config)
    fingerprints = mapping_fingerprints(build_repertoire(rows), kind, layout)
    srs.PROGRESS_FILE.write_text(json.dumps({"version": 4, "words": {
        "looks": entry(fingerprints["looks"], lapses=2, samples=[1, 2, 3]),
    }}))
    before = snapshot(path.parent)
    result = CliRunner().invoke(cli.app, ["-c", str(path), "difficult"])
    assert result.exit_code == 0, result.output
    assert "config.legacy" in result.output
    assert "1 current" in result.output
    assert "'looks': 'lk1'; base 'look', alt1" in result.output
    assert snapshot(path.parent) == before


def test_help_does_not_require_config_or_progress(tmp_path, monkeypatch):
    monkeypatch.setattr(srs, "PROGRESS_FILE", tmp_path / "progress.json")
    path = tmp_path / "missing" / "config.yaml"
    result = CliRunner().invoke(cli.app, ["-c", str(path), "difficult", "--help"])
    assert result.exit_code == 0, result.output
    assert "--limit" in result.output
    assert snapshot(tmp_path) == {}


def test_ordinary_config_validation_still_creates_csv_parent(tmp_path):
    target = tmp_path / "normal" / "chords.csv"
    Config.model_validate({"gen": {"file": str(target)}})
    assert target.parent.is_dir()
