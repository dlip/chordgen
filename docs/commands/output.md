# output

Outputs all the formats listed under `output.formats` in `config.yaml`. See
the [Output formats](../output-formats/qmk.md) section for per-format setup.

Each format writes one or more files into `~/.config/chordgen/`:

| Format         | Files                                |
| -------------- | ------------------------------------ |
| `qmk`          | `qmk_chords.def`                     |
| `zmk`          | `zmk_chords.dtsi`, `zmk_macros.dtsi` |
| `kanata`       | `kanata_chords.kbd`                  |
| `charachorder` | `charachorder_chords.json`           |
| `training`     | `training.txt`                       |
