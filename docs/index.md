# chordgen

Helps you to turn any keyboard into a chording-enabled device, and generates
chords that are optimised for your specific layout.

It supports standard keyboards and directional ones such as:

- [Harite](https://github.com/dlip/harite-v3)
- [CharaChorder](https://www.charachorder.com)
- [Svalboard](https://svalboard.com)

## Why chording?

We generally type words letter by letter which can be slow and error prone.
Chording is an alternate approach where multiple keys are pressed at the same
time and the word is outputted automatically. Stenography uses this approach
and lets the stenographer type in excess of 300 wpm — but the barrier to entry
is high because you can't use any of your existing typing skills.

chordgen's approach lets you type normally, but use chords for some words.
You learn words at your own pace and focus on the ones that will provide the
most benefit first.

## Where to next?

- [Quickstart](quickstart.md) — install and run the four core commands.
- [Chording approach](concepts/chording.md) — how chord/shift/alt keys work.
- [chords.csv](concepts/chords-csv.md) — the file you edit by hand.
- [Commands](commands/setup.md) — full reference for `setup`, `gen`,
  `output`, `train`, `drill`.
- [Output formats](output-formats/qmk.md) — wire chordgen into QMK / ZMK /
  Kanata / CharaChorder.
- [Configuration](configuration.md) — `config.yaml` schema.
