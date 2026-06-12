import csv
import logging
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

from chordgen.alt_generator import AltGenerator
from chordgen.assigner import assign_chords
from chordgen.config import Config, GenOptions
from chordgen.scorer import Scorer


def gen(options: GenOptions) -> None:
    scorer = Scorer(options)
    with open(options.file) as f:
        reader = csv.DictReader(f)
        print("Finding and scoring chords")
        chords = [line for line in reader]
        if len(chords) == 0:
            raise Exception("No rows found in chords file")
        with ProcessPoolExecutor() as executor:
            chords = list(
                tqdm(
                    executor.map(scorer.score, chords, chunksize=10),
                    total=len(chords),
                )
            )

    print("Generating alts")
    alt_generator = AltGenerator(options)
    with ProcessPoolExecutor() as executor:
        chords = list(
            tqdm(
                executor.map(alt_generator.add_alt, chords, chunksize=10),
                total=len(chords),
            )
        )

    print("Assigning chords")
    assign_chords(chords, options)

    print(f"Writing {options.file}")
    with open(options.file, "w", newline="") as f:
        # Union of every row's keys (rows read from existing CSVs may
        # have differing columns). Preserve first-row ordering and
        # append any extras seen later. The `debug` column is included
        # only when options.debug is set; when disabled we also drop
        # any stale debug values left over from a previous run.
        fieldnames: list[str] = []
        seen: set[str] = set()
        for row in chords:
            for k in row.keys():
                if k not in seen and k != "options":
                    seen.add(k)
                    fieldnames.append(k)
        if options.debug:
            if "debug" not in seen:
                fieldnames.append("debug")
        else:
            if "debug" in fieldnames:
                fieldnames.remove("debug")
            for row in chords:
                if "debug" in row:
                    row["debug"] = ""
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(chords)
