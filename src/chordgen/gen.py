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
        fieldnames = list(chords[0].keys())
        if "options" in fieldnames:
            fieldnames.remove("options")
        writer = csv.DictWriter(
            f, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(chords)
