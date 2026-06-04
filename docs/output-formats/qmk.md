# QMK

Output for [QMK](https://qmk.fm), a firmware for custom keyboards.
You can check my config
[here](https://github.com/dlip/qmk_firmware/tree/dlip/keyboards/mushi/keymaps/dlip)
for reference.

1. Set up chords as per this
   [gboards guide](https://combos.gboards.ca/docs/install/).
2. Add definitions for `KC_CHORD`, `KC_CHORD_SFT`, `KC_CHORD_ALT1`,
   `KC_CHORD_ALT2` thumb keys to your `keymap.c`. Feel free to change
   the actions to whatever works for you. If you have other special
   keys on your letters (e.g. home-row mods), add definitions for
   those too so they can be referred to in the script. Use these in
   your keymap.
3. Move the `#include "g/keymap_chord.h"` line below all your
   definitions:

   ```c
   #define KC_SFT_A MT(MOD_LSFT, KC_A)
   #define KC_ALT_S MT(MOD_LALT, KC_S)
   #define KC_GUI_D MT(MOD_LGUI, KC_D)
   #define KC_CTL_F MT(MOD_LCTL, KC_F)
   #define KC_CTL_J MT(MOD_LCTL, KC_J)
   #define KC_GUI_K MT(MOD_LGUI, KC_K)
   #define KC_ALT_L MT(MOD_LALT, KC_L)
   #define KC_SFT_SEMI MT(MOD_LSFT, KC_SEMI)

   #define KC_CHORD_ALT1 LT(1, KC_TAB)
   #define KC_CHORD_ALT2 LT(2, KC_SPC)
   #define KC_CHORD_SFT MT(MOD_LSFT, KC_BSPC)
   #define KC_CHORD C(KC_BSPC)

   #include "g/keymap_chord.h"
   ```

4. Define the custom key codes in `config.yaml`:

   ```yaml
   output:
     qmk:
       key_codes:
         A: KC_SFT_A
         S: KC_ALT_S
         D: KC_GUI_D
         F: KC_CTL_F
         J: KC_CTL_J
         K: KC_GUI_K
         L: KC_ALT_L
         ;: KC_SFT_SEMI
   ```

5. Copy the generated `~/.config/chordgen/qmk_chords.def` to your
   QMK keymap directory and add `#include "qmk_chords.def"` to the
   top of your QMK `chords.def` file.
6. Flash your keyboard.
