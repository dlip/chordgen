# Quickstart

```sh
pip install chordgen
chordgen setup     # downloads SUBTLEX-US, writes ~/.config/chordgen/{config.yaml, chords.csv}
chordgen gen       # picks an optimal chord per word and fills in alts
chordgen output    # writes firmware files for qmk / zmk / kanata / charachorder + training.txt
chordgen learn     # interactive TUI to drill chords with spaced repetition
chordgen drill     # speed-drill TUI for chords you have already learned
```

Edit `~/.config/chordgen/chords.csv` (remove words you don't want, pin
chords by hand, etc.) and re-run `gen` whenever you want to refresh.

See [Installation](#installation) below for non-pip workflows, and the
[Commands](commands/setup.md) section for full flags / behaviour.

## Installation

- Install [Python 3.11+](https://www.python.org/downloads/)
- Run `pip install chordgen` or `pip install -U chordgen` to upgrade
