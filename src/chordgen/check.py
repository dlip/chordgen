"""Read-only dictionary diagnostics, not a firmware or deployment validator."""

from __future__ import annotations

from collections import Counter, defaultdict
import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Literal

from fsrs import Card
import yaml

from chordgen import srs
from chordgen.chord import Chord, PracticeMapping, build_repertoire, mapping_fingerprints
from chordgen.config import Config
from chordgen.keyboard_view import resolve_keyboard_layout
from chordgen.output import assigned_rows


Severity = Literal["error", "warning", "info"]
CSV_FIELDS = ("word", "chord", "category", "frequency", "alt1", "alt2", "alt3")


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str
    examples: list[str] = field(default_factory=list)


@dataclass
class CheckReport:
    findings: list[Finding] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.findings)

    def add(self, severity: Severity, code: str, message: str, example: str = "") -> None:
        finding = next((f for f in self.findings if (f.severity, f.code) == (severity, code)), None)
        if finding is None:
            finding = Finding(severity, code, message)
            self.findings.append(finding)
        if example:
            finding.examples.append(example)


def _read_config(path: Path, report: CheckReport) -> Config | None:
    try:
        raw = yaml.safe_load(path.read_text())
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ValueError("configuration must be a mapping")
        if "train" in raw and "learn" not in raw:
            raw["learn"] = raw.pop("train")
            report.add("info", "config.legacy", "Legacy train settings interpreted as learn; file unchanged.")
        return Config.model_validate(raw)
    except (OSError, UnicodeError, ValueError, TypeError, yaml.YAMLError) as exc:
        report.add("error", "config.invalid", "Cannot read or validate configuration.", f"{path}: {exc}")
        return None


def _read_rows(path: Path, report: CheckReport) -> list[Chord] | None:
    rows = []
    invalid = False
    try:
        with path.open(newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            headers = reader.fieldnames or []
            missing = set(CSV_FIELDS) - set(headers)
            duplicates = [name for name, count in Counter(headers).items() if count > 1]
            if missing or duplicates or any(not name.strip() for name in headers):
                report.add("error", "csv.headers", "CSV requires unique headers and all seven chord columns; extra named columns are allowed.",
                           f"missing={sorted(missing)}, duplicate={duplicates}")
                return None
            for record, row in enumerate(reader, 1):
                if None in row or any(value is None for value in row.values()):
                    invalid = True
                    report.add("error", "csv.row", "CSV cells do not match its headers.",
                               f"record {record}, ending line {reader.line_num}")
                else:
                    rows.append(row)
    except (OSError, UnicodeError, csv.Error) as exc:
        report.add("error", "csv.invalid", "Cannot read dictionary CSV.", f"{path}: {exc}")
        return None
    # Dropping a malformed row would change exporter limit boundaries.
    return None if invalid else rows


def _read_progress(path: Path, report: CheckReport) -> dict | None:
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        report.add("info", "progress.absent", "No saved learning progress; fresh learning state.")
        return None
    except (OSError, UnicodeError, ValueError) as exc:
        report.add("error", "progress.invalid", "Cannot read learning progress; it has not been reset.", str(exc))
        return None
    if not isinstance(raw, dict) or raw.get("version") not in (2, 3, srs.PROGRESS_VERSION):
        report.add("error", "progress.version", "Unsupported progress structure/version; file unchanged.")
        return None
    if not isinstance(raw.get("words", {}), dict):
        report.add("error", "progress.invalid", "Progress words must be a mapping; file unchanged.")
        return None
    daily = raw.get("daily")
    if daily is not None and (not isinstance(daily, dict)
                             or not isinstance(daily.get("date"), str)
                             or any(type(daily.get(key)) is not int or daily[key] < 0
                                    for key in ("new_count", "review_count"))):
        report.add("error", "progress.daily", "Malformed daily quota state; file unchanged.")
    for key in ("speed_samples", "recall_speed_samples"):
        if key in raw and not isinstance(raw[key], list):
            report.add("error", "progress.samples", "Speed history must be a list; file unchanged.", key)
    return raw


def _check_progress(progress: dict | None, fingerprints: dict[str, str] | None, report: CheckReport) -> None:
    if progress is None:
        return
    matched = legacy = changed = removed = 0
    for word, entry in progress.get("words", {}).items():
        try:
            if not isinstance(entry, dict) or not isinstance(entry.get("card"), dict):
                raise ValueError("missing card object")
            if entry.get("mapping") is not None and not isinstance(entry["mapping"], str):
                raise ValueError("mapping identity must be a string")
            Card.from_dict(entry["card"])
            for key in ("reps", "lapses"):
                if key in entry and (type(entry[key]) is not int or entry[key] < 0):
                    raise ValueError(f"{key} must be a nonnegative integer")
            for key in ("wpm_ewma", "recall_wpm_ewma"):
                if entry.get(key) is not None and not isinstance(entry[key], (int, float)):
                    raise ValueError(f"{key} must be numeric or null")
            if "recall_seconds" in entry and not isinstance(entry["recall_seconds"], list):
                raise ValueError("recall_seconds must be a list")
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError) as exc:
            report.add("error", "progress.card", "Malformed learning card; no progress was changed.", f"{word!r}: {exc}")
            continue
        if fingerprints is None:
            continue
        if word not in fingerprints:
            removed += 1
            report.add("warning", "progress.unavailable", "Cards refer to words outside the current practice repertoire.", repr(word))
        elif not entry.get("mapping"):
            legacy += 1
            report.add("info", "progress.legacy", "Original mappings are unknown for legacy cards; continuity is not verified.", repr(word))
        elif not srs.mapping_matches(entry, fingerprints[word]):
            changed += 1
            report.add("warning", "progress.changed", "Saved mapping identities differ; these forms need relearning.", repr(word))
        else:
            matched += 1
    report.summary.append(f"Progress: {matched} matching, {legacy} unknown identity, {changed} changed, {removed} unavailable")
    if fingerprints is None:
        report.summary.append("Progress identity comparison unavailable: dictionary/layout invalid.")


def _check_rows(rows: list[Chord], report: CheckReport) -> bool:
    words = defaultdict(list)
    chords = defaultdict(list)
    valid = True
    for number, row in enumerate(rows, 1):
        word, chord = row["word"], row["chord"]
        label = f"record {number}: {word!r} ({chord!r})"
        if not word.strip() or any(c.isspace() for c in word):
            valid = False
            report.add("error", "word.invalid", "Word cells must contain a nonempty word without whitespace.", label)
        words[word.lower()].append(label)
        if not chord:
            continue
        if len(chord) != len(set(chord)):
            report.add("error", "chord.repeated-key", "An assigned chord repeats a key.", label)
        if "_" in chord or any(c.isspace() for c in chord):
            report.add("error", "chord.placeholder", "Assigned chords cannot contain placeholders or whitespace.", label)
        chords["".join(sorted(chord))].append(label)
    for labels in words.values():
        if len(labels) > 1:
            report.add("error", "word.duplicate", "Case-insensitive duplicate primary words; keep one authoritative row.", "; ".join(labels))
    for labels in chords.values():
        if len(labels) > 1:
            report.add("error", "chord.duplicate", "Assigned physical key sets collide, regardless of letter order.", "; ".join(labels))
    return valid


def _check_alts(rows: list[Chord], repertoire: dict[str, PracticeMapping], report: CheckReport) -> None:
    owners = defaultdict(list)
    for number, row in enumerate(rows, 1):
        if not row["chord"] or row["category"] == "contraction":
            continue
        for slot in range(1, 4):
            raw = row[f"alt{slot}"]
            word = raw.strip().lower()
            if not word:
                continue
            label = f"record {number}: {row['word']!r} + alt{slot} -> {raw!r}"
            if raw != raw.strip():
                report.add("warning", "alt.whitespace", "Leading/trailing alt whitespace makes emitted text differ from practice lookup.", label)
            if word == row["word"].lower():
                report.add("warning", "alt.self", "Alt duplicates its own primary word; practice uses the primary.", label)
                continue
            owners[word].append(label)
    for word, labels in owners.items():
        mapping = repertoire.get(word)
        chosen = f"practice uses {mapping.base!r} ({mapping.hint})" if mapping else "not in practice repertoire"
        if len(labels) > 1:
            report.add("warning", "alt.shared", "Multiple active alt slots emit the same form.", "; ".join(labels) + "; " + chosen)
        if mapping and mapping.slot == 0:
            report.add("warning", "alt.shadowed", "An assigned primary shadows an alt in practice.", "; ".join(labels) + "; " + chosen)


def _check_layout(config: Config, rows: list[Chord], report: CheckReport):
    kind, layout = resolve_keyboard_layout(config)
    options = getattr(config.gen.keyboard, kind)
    if kind == "standard":
        from chordgen.keyboards.standard import FINGER_MAPPING
        fingers = FINGER_MAPPING
    else:
        from chordgen.keyboards.directional import FINGER_MAPPING
        fingers = [row + [f + 5 if f else 0 for f in row[::-1]] for row in FINGER_MAPPING]
    labels = Counter(key for row in layout for key in row if key != "_")
    ambiguous = [key for key, count in labels.items() if count > 1]
    for key in ambiguous:
        report.add("error", "layout.duplicate", "Layout labels must identify one physical position (excluding _).", repr(key))
    dimensions_ok = (
        (len(layout) in (3, 4) and len({len(row) for row in layout[:3]}) == 1
         if kind == "standard" else len(layout) == len(fingers))
        and len(options.effort_map) >= len(layout)
        and all(0 < len(row) <= len(fingers[i]) and len(options.effort_map[i]) * 2 >= len(row)
                for i, row in enumerate(layout))
    )
    keyboard = None
    if dimensions_ok:
        try:
            keyboard = options.create()
        except (IndexError, KeyError, ValueError) as exc:
            report.add("error", "layout.shape", "Layout/effort geometry cannot construct the configured keyboard.", str(exc))
    else:
        report.add("error", "layout.shape", "Layout/effort dimensions do not fit the configured keyboard geometry.")
    if keyboard is None or ambiguous:
        report.summary.append("Chord comfort analysis unavailable: invalid/ambiguous layout.")
    finger_map = {key: fingers[r][c] for r, row in enumerate(layout) for c, key in enumerate(row)
                  if dimensions_ok and key != "_"}
    for number, row in enumerate(rows, 1):
        chord = row["chord"]
        if not chord:
            continue
        label = f"record {number}: {row['word']!r} ({chord})"
        missing = set(chord) - (set(labels) - {"_", " "})
        if missing:
            report.add("error", "chord.missing-key", "Assigned keys are absent from the configured layout; replacements are not reapplied.",
                       label + f": {sorted(missing)!r}")
            continue
        if keyboard is None or ambiguous:
            continue
        if keyboard.score(chord) < 0:
            report.add("warning", "chord.constraints", "Assigned chords violate current generation constraints; inspect intentional manual mappings.", label)
        counts = Counter(finger_map[key] for key in set(chord) if finger_map.get(key, 0) > 0)
        if any(n > 1 for n in counts.values()):
            report.add("info", "comfort.same-finger", "Multiple letter keys use one modeled finger; try these physically.", label)
        if kind == "standard" and keyboard.get_scissor_count(chord):
            report.add("info", "comfort.scissor", "Same-hand top/bottom-row combinations; comfort depends on your hardware.", label)
    return (kind, layout) if keyboard is not None and not ambiguous else None


def _check_exports(config: Config, rows: list[Chord], repertoire: dict[str, PracticeMapping], report: CheckReport) -> None:
    all_rows = assigned_rows(rows)
    # Frequency is not part of export identity.
    def identity(mapping):
        return (mapping.word, mapping.base, "".join(sorted(mapping.chord)), mapping.slot)

    expected = {identity(mapping) for mapping in repertoire.values()}
    for name in dict.fromkeys(config.output.formats):
        output = getattr(config.output, name)
        selected = assigned_rows(rows, output.limit) if name in {"zmk", "kanata"} else all_rows
        primary_only = name in {"charachorder", "training"}
        if name == "training":
            selected = all_rows[:len(all_rows) // 10 * 10]
        if len(selected) < len(all_rows):
            report.add("warning", f"export.{name}.omitted", "Assigned rows omitted by the configured limit or training's incomplete final block.",
                       f"{len(all_rows) - len(selected)} rows omitted")
        if primary_only:
            report.add("info", f"export.{name}.primary-only", "This format exports primary forms only, not alt practice mappings.")
        bindings = {}
        blocked = False

        def bind(keys, label):
            nonlocal blocked
            if any(not key or key.isspace() for key in keys) or len(keys) != len(set(keys)):
                blocked = True
                report.add("error", f"export.{name}.binding", "A trigger contains empty or repeated resolved keys.", label)
            physical = tuple(sorted(keys))
            if physical in bindings:
                blocked = True
                report.add("error", f"export.{name}.collision", "Multiple bindings resolve to the same trigger.", f"{bindings[physical]}; {label}")
            else:
                bindings[physical] = label

        if name == "zmk":
            positions = [key for row in output.key_positions for key in row if key not in " _"]
            duplicates = [key for key, n in Counter(positions).items() if n > 1]
            if duplicates:
                blocked = True
                report.add("error", "export.zmk.positions", "Repeated ZMK labels ambiguously resolve to the last position.", repr(duplicates))
            for punctuation in ";,.":
                if punctuation in output.position_map():
                    try:
                        bind(output.translate_keys([punctuation] + output.chord_keys), f"built-in punctuation {punctuation!r}")
                    except ValueError as exc:
                        blocked = True
                        report.add("error", "export.zmk.translation", "Configured key translation fails.", str(exc))
        emitted = set()
        for row in selected:
            forms = [(0, row["word"])]
            if not primary_only:
                forms += [(slot, row[f"alt{slot}"]) for slot in range(1, 4) if row[f"alt{slot}"]]
            for slot, word in forms:
                if row["category"] != "contraction":
                    emitted.add(identity(PracticeMapping(word, row["word"], row["chord"], slot)))
                if name not in {"qmk", "zmk", "kanata"}:
                    continue
                alt = getattr(output, f"alt{slot}_keys") if slot else []
                variants = [("normal", output.chord_keys)]
                if output.shifted_chord_keys and row["category"] != "contraction":
                    variants.append(("shifted", output.shifted_chord_keys))
                for variant, trigger in variants:
                    label = f"{row['word']!r} + slot{slot} -> {word!r} ({variant})"
                    try:
                        if name == "qmk":
                            keys = output.translate_keys(row["chord"]) + trigger + alt
                        elif name == "kanata":
                            keys = output.translate_chord(row["chord"]) + trigger + alt
                        else:
                            keys = output.translate_keys(list(row["chord"]) + trigger + alt)
                        bind(keys, label)
                    except Exception as exc:
                        # QMK's existing translation API raises a plain Exception.
                        blocked = True
                        report.add("error", f"export.{name}.translation", "Configured key translation fails.", f"{label}: {exc}")
        missing = expected - emitted
        report.summary.append(f"Export {name}: {'BLOCKED; ' if blocked else ''}{len(expected & emitted)}/{len(expected)} practice mappings selected"
                              + (" (selection only, not usable coverage)" if blocked else ""))
        unsupported = {identity(m) for m in repertoire.values() if primary_only and m.slot}
        for word, base, chord, slot in sorted(missing - unsupported):
            report.add("warning", f"export.{name}.coverage", "Current practice mappings are absent from this configured export.",
                       f"{word!r}: {base!r} ({chord}), slot {slot}")
    if not config.output.formats:
        report.add("info", "export.none", "No output formats enabled; export coverage not checked.")


def check_dictionary(config: Config, rows: list[Chord], progress: dict | None = None) -> CheckReport:
    """Inspect complete CSV rows without modifying rows, configuration, or cards."""
    report = CheckReport()
    valid = _check_rows(rows, report)
    repertoire = build_repertoire(rows) if valid else {}
    assigned = assigned_rows(rows)
    report.summary.append(f"Dictionary: {len(rows)} rows, {len(assigned)} assigned; "
                          f"practice: {sum(m.slot == 0 for m in repertoire.values())} primary, "
                          f"{sum(m.slot != 0 for m in repertoire.values())} alt")
    lengths = Counter(len(row["chord"]) for row in assigned)
    report.summary.append("Letter-key chord lengths (excluding trigger/modifiers): "
                          + (", ".join(f"{length}: {count}" for length, count in sorted(lengths.items())) or "none"))
    for number, row in enumerate(rows, 1):
        if len(row["chord"]) >= 4:
            report.add("info", "comfort.long", "Four or more letter keys; inspect comfort before learning.",
                       f"record {number}: {row['word']!r} ({row['chord']})")
    resolved = _check_layout(config, rows, report)
    if valid:
        _check_alts(rows, repertoire, report)
        _check_exports(config, rows, repertoire, report)
    else:
        report.summary.append("Practice and export coverage unavailable: invalid word cells.")
    fingerprints = mapping_fingerprints(repertoire, *resolved) if valid and resolved else None
    _check_progress(progress, fingerprints, report)
    return report


def run_check(config_path: Path, *, progress_path: Path | None = None) -> CheckReport:
    report = CheckReport()
    config = _read_config(config_path, report)
    progress = _read_progress(srs.PROGRESS_FILE if progress_path is None else progress_path, report)
    rows = _read_rows(config.gen.file, report) if config else None
    if config is not None and rows is not None:
        result = check_dictionary(config, rows, progress)
        report.findings.extend(result.findings)
        report.summary.extend(result.summary)
    else:
        report.summary.append("Dictionary, layout, and export analysis unavailable: input validation failed.")
        _check_progress(progress, None, report)
    return report


def format_check(report: CheckReport, limit: int = 10) -> str:
    if limit < 1:
        raise ValueError("limit must be positive")
    lines = ["Chordgen health check", *report.summary]
    for severity, title in (("error", "Errors"), ("warning", "Warnings"), ("info", "Information")):
        findings = sorted((f for f in report.findings if f.severity == severity), key=lambda f: f.code)
        lines.append(f"\n{title}: {len(findings)} diagnostic groups")
        for finding in findings:
            lines.append(f"  [{finding.code}] {finding.message}")
            lines.extend(f"    {example}" for example in finding.examples[:limit])
            if len(finding.examples) > limit:
                lines.append(f"    ... {len(finding.examples) - limit} more ({len(finding.examples)} total)")
    lines.append("\nRead-only: no files changed. Export selection is not a firmware compilation/deployment check.")
    return "\n".join(lines)
