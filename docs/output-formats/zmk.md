# ZMK

Output for [ZMK](https://zmk.dev/), a firmware for custom keyboards.

1. Copy the generated `~/.config/chordgen/zmk_chords.dtsi` and
   `~/.config/chordgen/zmk_macros.dtsi` to your zmk keymap directory.
2. Include these lines in your zmk keymap file:

   ```dts
   macros {
     #include "macros.dtsi"
   };

   chords {
     compatible = "zmk,chords";
     #include "chords.dtsi"
   };
   ```

3. Include these lines in your zmk keymap conf file. You may have to
   increase `CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY` if you are able to
   fit more chords on your controller:

   ```conf
   CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY=512
   CONFIG_ZMK_CHORD_MAX_KEYS_PER_CHORD=10
   CONFIG_ZMK_CHORD_MAX_PRESSED_CHORDS=10
   ```

4. Flash your keyboard.
