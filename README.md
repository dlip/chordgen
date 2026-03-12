# Chordgen

Helps you to turn any keyboard into a chording enabled device, and generates chords that are optimized for your specific layout.

It supports standard keyboards and directional ones such as:

- [Harite](https://github.com/dlip/harite-v3)
- [CharaChorder](https://www.charachorder.com)
- [Svalboard](https://svalboard.com)

## Introduction

We generally type words letter by letter which can be slow and error prone, chording is a alternate approach where multiple keys are pressed at the same time and the word is outputted automatically. Stenography, which uses this approach is often used in court reporting, and allows the stenographer to type in excess of 300 wpm. The downside is that since it so specialised, there is a large barrier to entry because you can't use any of your existing typing skills.

Chordgen's approach allows you to type normally, but then use chords for some words. This allows you to learn words at your own pace, and focus on the ones that will provide the most benefit first.

## Chording Approach

In order to distinguish normal typing from a chord, it defines chord, shift, and alt1/2 keys that are pressed in combination with the chord to get the desired output. These keys work well on the thumbs to ensure all the combinations are possible to be press with them.

| Input                           | Output           |
| ------------------------------- | ---------------- |
| l + chord                       | look`<space>`    |
| l + chord + shift               | Look`<space>`    |
| l + chord + alt1                | looked`<space>`  |
| l + chord + alt2                | looking`<space>` |
| l + chord + alt1 + alt2         | looks`<space>`   |
| l + chord + shift + alt1 + alt2 | Looks`<space>`   |

This is how I have set up my 4 key thumb cluster from left to right:

- alt1 (normally tab on tap or my navigation/number/symbol layer on hold, with hold preferred setting)
- alt2 (normally space on tap or my media/function layer on hold, with tap preferred setting)
- shift (normally backspace on tap or shift on hold, with hold preferred setting)
- chord (normally delete word, this is great when making mistakes while learning)

## Process

Chordgen takes a `chords.csv` file such as the following then automatically selects the best chords for your keyboard and layout, then adds alternate chords depending on what type of word it is. You can reserve chords if you want to use a particular chord for a word too.

| word | chord | reserved_chord | type  | alt1 | alt2 | alt3 |
| ---- | ----- | -------------- | ----- | ---- | ---- | ---- |
| the  |       |                | DET   |      |      |      |
| and  |       |                | CCONJ |      |      |      |
| have |       |                | VERB  |      |      |      |

Automatically becomes

| word | chord | reserved_chord | type  | alt1 | alt2 | alt3   |
| ---- | ----- | -------------- | ----- | ---- | ---- | ------ |
| the  | t     |                | DET   |      |      |        |
| and  | a     |                | CCONJ |      |      |        |
| have | h     |                | VERB  | has  | had  | having |

This file is then used to output to a format that can be used by various programmable keyboards, or even software remapping with Kanata

## Installation

- Install [Python 3.11+](https://www.python.org/downloads/)
- Run `pip install chordgen`

## Usage

Run `chordgen COMMAND` using one of the commands below

### setup

Run this first to create `config.yaml` with all the default options.

Read the [schema](./schema.md) and my [dotfiles](https://github.com/dlip/dotfiles/tree/main/.config/chordgen) to understand the options.

### gen

Generates chords and alts for `chords.csv`. It will copy the [default](./src/chordgen/assets/chords.csv) file if you do not provide one.

The approach it uses is:

- Generate all combinations of the letters in the word which start with the first letter and keep the order from left to right
- Reject chords that have already been used
- Reject chords that are shorter than a minimum amount of characters
- Score remaining chords by effort and select the best option depending on your particular keyboard layout
- Add alt versions

### output

Outputs all the formats listed under `output.formats` in `config.yaml`. See [output formats](#output-formats) below for more information.

#### Output Formats

##### qmk

This is an output for [QMK](https://qmk.fm) which is a firmware for custom keyboards.

You can check my config [here](https://github.com/dlip/qmk_firmware/tree/dlip/keyboards/mushi/keymaps/dlip) for reference

- Setup chords as per this [gboards guide](https://combos.gboards.ca/docs/install/)
- Add definitions for KC_CHORD, KC_CHORD_SFT, KC_CHORD_ALT1, KC_CHORD_ALT2 thumb keys to your `keymap.c`. Feel free to change the actions here to whatever works for you. If you have other special keys on your letters eg. home row mods, add definitions for these also so they can be referred to in the script. Use these in your keymap.

- Move the `#include "g/keymap_chord.h"` line below all your definitions

```
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

- Define the custom key codes in `config.yaml`

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

- Copy the generated `~/.config/chordgen/qmk_chords.def` to your QMK keymap directory
- Add `#include "qmk_chords.def"` to the top of your QMK `chords.def` file
- Flash your keyboard

##### zmk

This is an output for [ZMK](https://zmk.dev/) which is a firmware for custom keyboards.

- Copy the generated `~/.config/chordgen/zmk_chords.dtsi` and `~/.config/chordgen/zmk_macros.dtsi` to your zmk keymap directory
- Include these lines in your zmk keymap keymap file

```
  macros {
    #include "macros.dtsi"
  };

  chords {
    compatible = "zmk,chords";
    #include "chords.dtsi"
  };
```

- Include these lines in your zmk keymap conf file, you may have to increase `CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY` if you are able to fit more chords on your controller

```
CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY=512
CONFIG_ZMK_CHORD_MAX_KEYS_PER_CHORD=10
CONFIG_ZMK_CHORD_MAX_PRESSED_CHORDS=10
```

- Flash your keyboard

##### kanata

This is an output for [Kanata](https://github.com/jtroo/kanata) which is a software keyboard remapper. Be aware that many keyboards, especially laptop ones do not support having many keys held at the same time. You can check what combinations work for your one [here](https://www.mechanical-keyboard.org/key-rollover-test/)

- Copy the generated `~/.config/chordgen/kanata_chords.kbd` to your keymap directory
- Add to your keymap:

  ```
  (defcfg concurrent-tap-hold yes)
  (include kanata_chords.kbd)
  ```

- Run `sudo kanata -c <keymap.kbd>`

##### charachorder

This in an output for [CharaChorder](https://www.charachorder.com/) which supports their directional and standard keyboard designs. Since it already has its own way of handling alts built in, only the base word is outputted.

- When running `gen` change the `config.yaml` `gen.keyboard.type` to directional and `gen.min_chord_length` to 2
- Disable `output.formats` other than charachorder and training.
- Open the [Chords Manager](https://charachorder.io/config/chords/)
- If there are existing chords, press Clear Chords and apply
- Import `~/.config/chordgen/charachorder_chords.json`
- Apply

##### training

This generates a [training.txt](training.txt) file for you to copy a line of 10 words at a time into a typing practice tool like [Monkeytype](https://monkeytype.com/) custom mode to help learn the chords:

```
the and you have that for with this not but
t   a   y   h    th   f   w    ti   n   b
```
