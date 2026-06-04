# Kanata

Output for [Kanata](https://github.com/jtroo/kanata), a software
keyboard remapper. Be aware that many keyboards, especially laptop
ones, do not support having many keys held at the same time. You can
check what combinations work for yours
[here](https://www.mechanical-keyboard.org/key-rollover-test/).

1. Copy the generated `~/.config/chordgen/kanata_chords.kbd` to your
   keymap directory.
2. Add to your keymap:

   ```lisp
   (defcfg concurrent-tap-hold yes)
   (include kanata_chords.kbd)
   ```

3. Run `sudo kanata -c <keymap.kbd>`.
