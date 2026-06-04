# Chordgen

Helps you to turn any keyboard into a chording enabled device, and generates chords that are optimized for your specific layout.

It supports standard keyboards and directional ones such as:

- [Harite](https://github.com/dlip/harite-v3)
- [CharaChorder](https://www.charachorder.com)
- [Svalboard](https://svalboard.com)

## Quickstart

```sh
pip install chordgen
chordgen setup     # downloads SUBTLEX-US, writes ~/.config/chordgen/{config.yaml, chords.csv}
chordgen gen       # picks an optimal chord per word and fills in alts
chordgen output    # writes firmware files for qmk / zmk / kanata / charachorder + training.txt
chordgen train     # interactive TUI to drill chords with spaced repetition
```

Edit `~/.config/chordgen/chords.csv` (remove words you don't want, pin
chords by hand, etc.) and re-run `gen` whenever you want to refresh.

## Introduction

We generally type words letter by letter which can be slow and error prone, chording is a alternate approach where multiple keys are pressed at the same time and the word is outputted automatically. Stenography, which uses this approach is often used in court reporting, and allows the stenographer to type in excess of 300 wpm. The downside is that since it so specialised, there is a large barrier to entry because you can't use any of your existing typing skills.

Chordgen's approach allows you to type normally, but then use chords for some words. This allows you to learn words at your own pace, and focus on the ones that will provide the most benefit first.

## Chording Approach

In order to distinguish normal typing from a chord, it defines chord, shift, and alt1/2 keys that are pressed in combination with the chord to get the desired output. These keys work well on the thumbs to ensure all the combinations are possible to be pressed with them.

| Input                           | Output           |
| ------------------------------- | ---------------- |
| l + chord                       | look`<space>`    |
| l + chord + shift               | Look`<space>`    |
| l + chord + alt1                | looked`<space>`  |
| l + chord + alt2                | looking`<space>` |
| l + chord + alt1 + alt2 (alt3)  | looks`<space>`   |
| l + chord + shift + alt1 + alt2 | Looks`<space>`   |

This is how I have set up my 4 key thumb cluster from left to right:

- alt1 (normally tab on tap or my navigation/number/symbol layer on hold, with hold preferred setting)
- alt2 (normally space on tap or my media/function layer on hold, with tap preferred setting)
- shift (normally backspace on tap or shift on hold, with hold preferred setting)
- chord (normally delete word, this is great when making mistakes while learning)

## Process

Chordgen takes a `chords.csv` file such as the following then automatically selects the best chords for your keyboard and layout, then adds alternate chords depending on what type of word it is.

| word | chord | category | frequency | alt1 | alt2 | alt3 |
| ---- | ----- | -------- | --------- | ---- | ---- | ---- |
| the  |       | det      | 7.40      |      |      |      |
| and  |       | cconj    | 7.18      |      |      |      |
| have |       | verb     | 6.78      |      |      |      |

Automatically becomes

| word | chord | category | frequency | alt1 | alt2 | alt3   |
| ---- | ----- | -------- | --------- | ---- | ---- | ------ |
| the  | t     | det      | 7.40      |      |      |        |
| and  | and   | cconj    | 7.18      |      |      |        |
| have | hv    | verb     | 6.78      | has  | had  | having |

The exact chord picked for each word depends on contention with the
rest of the file: `have` ends up as `hv` because higher-frequency `h`
words further down (e.g. `huh`) get the single-letter `h` chord.

This file is then used to output to a format that can be used by
various programmable keyboard firmwares (QMK, ZMK, CharaChorder) or
software remapping (Kanata).

### Reserving a chord

If you want to pin a particular chord to a word, add a row by hand with the `chord` column filled in and the `frequency` column **left empty**. An empty `frequency` is the signal that the row was added by you, so `gen` will keep your chord exactly as written and just generate alts for it. For example:

| word  | chord | category | frequency | alt1 | alt2 | alt3 |
| ----- | ----- | -------- | --------- | ---- | ---- | ---- |
| email | em    | noun     |           |      |      |      |

To re-pin a word that already has a generated chord, just clear its `frequency` cell and edit the `chord`.

### Editing chords.csv

After `setup`, `chords.csv` is yours. Common workflows:

- **Removing a word** — delete the row.
- **Pinning a chord** — add a row by hand with the `chord` column set
  and the `frequency` column left empty. See [Reserving a chord](#reserving-a-chord).
- **Adjusting category or alts** — edit the `category` cell or
  pre-fill `alt1`–`alt3`. By default `gen` keeps non-empty alt slots
  as written; set `gen.alts.overwrite: true` in `config.yaml` to force
  regeneration on every run.
- **Re-running** — `chordgen gen` is idempotent. Non-reserved chord
  cells are cleared before solving, so any change to a row's word,
  category, frequency, or alts takes effect on the next run.

## Installation

- Install [Python 3.11+](https://www.python.org/downloads/)
- Run `pip install chordgen` or `pip install -U chordgen` to upgrade

## Usage

Run `chordgen COMMAND` using one of the commands below

### setup

Creates `~/.config/chordgen/config.yaml` and downloads a
frequency-ranked `chords.csv` from SUBTLEX. After `setup`, `chords.csv`
is yours to edit by hand.

Flags:

| Flag              | Default      | Purpose                                                            |
| ----------------- | ------------ | ------------------------------------------------------------------ |
| `--source`        | `subtlex-us` | Vocabulary source. Also: `subtlex-uk`.                             |
| `--size`          | `2000`       | Number of words to keep.                                           |
| `--min-frequency` | `3.0`        | Drop words below this Zipf score (3.0 ≈ 1 occurrence per million). |
| `--force`         | off          | Overwrite an existing `chords.csv`.                                |

Read the [schema](./schema.md) and my
[dotfiles](https://github.com/dlip/dotfiles/tree/main/.config/chordgen)
to understand the rest of the options.

### gen

Generates chords and alts for `chords.csv` in-place.

The pipeline runs in three phases:

1. **Score** — for each word, enumerate every chord that keeps the
   first letter and preserves left-to-right order, then score each
   candidate using the configured keyboard layout (effort per key,
   same-row / same-column / scissor / directional penalties).
2. **Generate alts** — based on the word's `category` (verb, noun,
   adjective, adverb), fill `alt1`–`alt3` with inflected forms (e.g.
   `look → looks, looked, looking`). Alt slots already filled by hand
   are kept by default.
3. **Assign** — solve a sparse minimum-cost bipartite matching so
   each word gets a unique chord and the total `score × frequency` is
   globally minimised. Frequent words attract short / low-effort
   chords. Words for which every viable chord is already cheaper for
   another word are reported in the diagnostics.

By default the matcher runs a single global pass that minimises total
`score × frequency`. If you find rare words bumping common ones onto
longer chords, set `gen.assignment.priority_tiers` in `config.yaml`
(e.g. `[500, 1000]`) to solve in tiers — top 500 most-frequent words
first, then the next 500, then the rest, with each tier's chords
reserved out of the next. This protects common words like `the` /
`and` / `have` from being out-bid by rare words competing for the
same key.

### output

Outputs all the formats listed under `output.formats` in `config.yaml`. See the per-format sections below for more information.

Each format writes one or more files into `~/.config/chordgen/`:

| Format         | Files                                |
| -------------- | ------------------------------------ |
| `qmk`          | `qmk_chords.def`                     |
| `zmk`          | `zmk_chords.dtsi`, `zmk_macros.dtsi` |
| `kanata`       | `kanata_chords.kbd`                  |
| `charachorder` | `charachorder_chords.json`           |
| `training`     | `training.txt`                       |

#### qmk

Output for [QMK](https://qmk.fm), a firmware for custom keyboards. You can check my config [here](https://github.com/dlip/qmk_firmware/tree/dlip/keyboards/mushi/keymaps/dlip) for reference.

1. Set up chords as per this [gboards guide](https://combos.gboards.ca/docs/install/).
2. Add definitions for `KC_CHORD`, `KC_CHORD_SFT`, `KC_CHORD_ALT1`, `KC_CHORD_ALT2` thumb keys to your `keymap.c`. Feel free to change the actions to whatever works for you. If you have other special keys on your letters (e.g. home-row mods), add definitions for those too so they can be referred to in the script. Use these in your keymap.
3. Move the `#include "g/keymap_chord.h"` line below all your definitions:

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

5. Copy the generated `~/.config/chordgen/qmk_chords.def` to your QMK keymap directory and add `#include "qmk_chords.def"` to the top of your QMK `chords.def` file.
6. Flash your keyboard.

#### zmk

Output for [ZMK](https://zmk.dev/), a firmware for custom keyboards.

1. Copy the generated `~/.config/chordgen/zmk_chords.dtsi` and `~/.config/chordgen/zmk_macros.dtsi` to your zmk keymap directory.
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

3. Include these lines in your zmk keymap conf file. You may have to increase `CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY` if you are able to fit more chords on your controller:

   ```conf
   CONFIG_ZMK_CHORD_MAX_CHORDS_PER_KEY=512
   CONFIG_ZMK_CHORD_MAX_KEYS_PER_CHORD=10
   CONFIG_ZMK_CHORD_MAX_PRESSED_CHORDS=10
   ```

4. Flash your keyboard.

#### kanata

Output for [Kanata](https://github.com/jtroo/kanata), a software keyboard remapper. Be aware that many keyboards, especially laptop ones, do not support having many keys held at the same time. You can check what combinations work for yours [here](https://www.mechanical-keyboard.org/key-rollover-test/).

1. Copy the generated `~/.config/chordgen/kanata_chords.kbd` to your keymap directory.
2. Add to your keymap:

   ```lisp
   (defcfg concurrent-tap-hold yes)
   (include kanata_chords.kbd)
   ```

3. Run `sudo kanata -c <keymap.kbd>`.

#### charachorder

Output for [CharaChorder](https://www.charachorder.com/) directional and standard keyboards. Since CharaChorder handles alts internally, only the base word is emitted.

1. Before running `gen`, set `gen.keyboard.type` to `directional` and `gen.min_chord_length` to `2` in `config.yaml`.
2. Disable `output.formats` other than `charachorder` and `training`.
3. Open the [Chords Manager](https://charachorder.io/config/chords/).
4. If there are existing chords, press Clear Chords and apply.
5. Import `~/.config/chordgen/charachorder_chords.json` and apply.

#### training

Note: Check the `train` command below for the new approach

Plain-text drill file for typing-practice tools like [Monkeytype](https://monkeytype.com/) custom mode. Copy a line of 10 words at a time into the tool to help learn the chords:

```text
the and you have that for with this not but
t   a   y   h    th   f   w    ti   n   b
```

### train

![Training](./images/training.png)

Interactive typing-practice TUI that drills your chords using
spaced repetition. Long-term scheduling is backed by
[py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) (the FSRS
algorithm); in-session repetition rides on FSRS's own
learning / relearning steps. Words flow horizontally across the
screen — type each word followed by a space, and the next one is
appended.

The session model mirrors Anki: each calendar day has a budget of
`new_words_per_day` brand-new words and `reviews_per_day` overdue
reviews. The session ends when the budget is empty and any in-flight
learning words have graduated.

- Words are picked first from cards that are overdue in the FSRS
  schedule (sorted by retrievability), then from words your typing
  speed has flagged as slow, then by descending frequency for words
  you've never seen. Each bucket is capped by the day's remaining
  review / new budget.
- New / learning words show their chord directly under the word.
  Once a word has graduated to FSRS Review state and accumulated
  `train.mastery_threshold` total reviews, the chord is hidden until
  you lapse on it again.
- Any mistake during a word grades the review as `Again`, sending the
  card back into the learning queue. An `Again` on a card already in
  Review counts as a *lapse*; words that accumulate
  `train.leech_threshold` lapses are flagged as **leeches** in the
  session summary so you can re-pin or revise the chord in
  `chords.csv`.
- Per-word speed grading: the WPM of each clean word is compared to a
  rolling median of recent samples. Words below
  `train.slow_wpm_fraction` of the median are graded `Hard` (instead
  of `Good`) so FSRS schedules them sooner. The first word of a
  session and any word that flashed red are excluded from speed
  grading.
- When a word is rescheduled mid-session it's appended to the tail of
  the visible queue rather than inserted right after the current word,
  so the next word doesn't flip under your fingers.
- Under the chord row you'll see three Anki-style counts of the
  on-screen queue: blue = new, red = learning / relearning, green =
  graduated.
- Progress is persisted to `~/.config/chordgen/progress.json` after
  every word commit, so quitting mid-session never loses your daily
  counters or FSRS state. Press `Esc` or `Ctrl+C` at any time to quit.
- Once the day's quota is exhausted you land on a "No more words due
  today!" screen — there's no per-session summary, because the train
  mode is about long-term retention rather than speed tests. For
  speed practice on words you already know, use the separate
  [`chordgen drill`](#drill) mode below.

Useful keys during a session:

| Key              | Action                          |
| ---------------- | ------------------------------- |
| any letter       | type next character of the word |
| `Space`          | commit a fully-typed word       |
| `Backspace`      | undo last letter                |
| `Ctrl+W`         | clear the current word  (I recommend binding alt/ctrl backspace in your terminal to this and making a dedicated key on your keybord if it is programmable)         |
| `Esc` / `Ctrl+C` | quit the trainer                |

Relevant `config.yaml` knobs (under `train`):

| Key                  | Default | Purpose                                                                                |
| -------------------- | ------- | -------------------------------------------------------------------------------------- |
| `show_words`         | 10      | Number of words shown on screen at once.                                               |
| `new_words_per_day`  | 20      | Daily cap on brand-new words introduced (Anki-style).                                  |
| `reviews_per_day`    | 200     | Daily cap on overdue / re-drilled review words surfaced.                               |
| `leech_threshold`    | 8       | Lapses (Again on a graduated card) before a word is flagged as a leech. 0 to disable.  |
| `mastery_threshold`  | 3       | Total FSRS reviews before the chord is hidden for a graduated word.                    |
| `relearn_steps`      | 3       | Number of FSRS relearning steps after a lapse (in-session re-drills).                  |
| `target_retention`   | 0.9     | FSRS desired retention rate; affects long-term interval lengths.                       |
| `slow_wpm_fraction`  | 0.7     | Fraction of the rolling-median WPM under which a word is graded `Hard`.                |
| `slow_min_samples`   | 20      | Minimum WPM samples collected before slow-grading kicks in.                            |

### drill

Speed-drill TUI for words you've already learned. Drill mode is
**read-only** — it doesn't touch FSRS state, lapse counters, or
daily quotas. Use it as a warm-up or to benchmark your typing speed
against the chords you already know.

- The word pool is restricted to words whose FSRS card is in
  Review state (i.e. graduated through the train mode). If no
  graduated words exist yet, drill prompts you to run
  `chordgen train` first.
- Words are picked by random shuffle from that pool.
- A drill ends after a fixed number of words (`drill.mode = count`,
  using `drill.count`) or after a fixed amount of time
  (`drill.mode = time`, using `drill.time_seconds`). The default is
  a 30-second timed drill.
- The summary screen reports WPM, accuracy (correct / total), and
  any words you fumbled. Press `Tab` to start another drill (Tab
  also restarts mid-drill if you want to bail out), or `Esc` /
  `Ctrl+C` to quit.

Relevant `config.yaml` knobs (under `drill`):

| Key                  | Default | Purpose                                                                       |
| -------------------- | ------- | ----------------------------------------------------------------------------- |
| `show_words`         | 10      | Number of words shown on screen at once.                                      |
| `mode`               | `time`  | `count` ends after a fixed number of words; `time` ends after a fixed timer.  |
| `count`              | 25      | Words to drill when `mode = count`.                                           |
| `time_seconds`       | 30      | Drill length in seconds when `mode = time`.                                   |

## Development

### Clone the repo

```sh
git clone https://github.com/dlip/chordgen.git
cd chordgen
```

### Nix

- Install [Nix](https://nixos.org/download/) or use NixOS
- Add `devenv` to your packages
- Run `devenv shell` or use the [shell hook](https://devenv.sh/auto-activation/)

### Non-nix

- Install [Python 3.11.14](https://www.python.org/downloads/release/python-31114/)
- Install UV

```sh
pip install uv
```

### Running

```sh
uv run chordgen --help
```

### Tests

```sh
uv sync --extra dev
uv run pytest
```
