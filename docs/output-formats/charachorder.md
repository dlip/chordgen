# CharaChorder

Output for [CharaChorder](https://www.charachorder.com/) directional
and standard keyboards. Since CharaChorder handles alts internally,
only the base word is emitted.

1. Before running `gen`, set `gen.keyboard.type` to `directional` and
   `gen.min_chord_length` to `2` in `config.yaml`.
2. Disable `output.formats` other than `charachorder` and `training`.
3. Open the [Chords Manager](https://charachorder.io/config/chords/).
4. If there are existing chords, press Clear Chords and apply.
5. Import `~/.config/chordgen/charachorder_chords.json` and apply.
