# add

Interactively add words to `chords.csv`. Useful for one-off
additions (a name, a domain term, a missing inflection) without
re-running the full `chordgen gen` pipeline.

## Usage

```sh
chordgen add WORD [WORD ...]
chordgen add --words-file path/to/words.txt
```

Words from `WORDS` and `--words-file` are combined and processed
in order.

## Behaviour

For each input word `chordgen add` does the following:

1. **Skip if already known.** If the word already appears in
   `chords.csv` (as a `word` row or any non-empty `alt1` / `alt2`
   / `alt3`), prints a notice and moves on.
2. **Auto-detect category.** Closed-class words (modal /
   demonstrative / number / pronoun / contraction) are looked up
   in the same retag table the SUBTLEX pipeline uses; everything
   else falls through to `pattern.en`'s POS tagger and is mapped
   to verb / noun / adjective / adverb. Anything else becomes
   the empty category (no alts).
3. **Override the category.** Shows a numbered menu with the
   auto-detected choice marked. Press Enter to accept, or type a
   number to override.
4. **Show collision-free chord options.** Scores the word against
   the configured keyboard, drops any chord that collides with a
   chord already in `chords.csv` (sorted-key comparison) or is
   shorter than `gen.min_chord_length`, and lists the top ten
   ranked by ascending score.
5. **Pick or type a chord.** Type a number, press Enter to accept
   the top option, or type a custom chord. Custom chords are
   validated through the same scorer the assigner uses (first
   letter must match, every key must be on the keyboard,
   collisions blocked, length floor enforced). The buffer is
   coloured **red** while it's invalid and **green** the moment
   it becomes a valid choice — and the reason it's invalid (e.g.
   `(first letter must match …)`, `(collides with an existing
   chord)`) is shown live next to the buffer. Submit with Enter.
6. **Generate alts.** Runs `AltGenerator` with the chosen
   category. Any alt slot whose generated form collides with an
   existing word is dropped (the row is still appended).
7. **Append and flush.** Writes the new row with the chord
   pinned and `frequency` left empty, so future `chordgen gen`
   runs treat it as a user-pinned reserved row and won't
   reassign it. The CSV is rewritten atomically after every
   accepted word — Ctrl+C mid-batch keeps the words already
   accepted.

## Example

```sh
$ chordgen add banana
Category for 'banana' (auto: noun):
  [1] (none)
  [2] verb
  [3] noun *
  [4] adjective
  [5] adverb
  [6] pronoun
  [7] demonstrative
  [8] modal
  [9] number
  [10] contraction
Pick category [Enter to accept auto]:

Chord options for 'banana':
  [1] ba   score=12
  [2] bn   score=15
  [3] bna  score=18
  ...
Pick a number, type a custom chord, or Enter to accept the top option.
Chord:

+ banana -> ba (alt1=bananas, alt2=, alt3=)
Added 1 word
```

## Tips

- Pair with `--words-file` to import a list you've been
  collecting — one word per line works.
- The CSV is rewritten in place; back up `chords.csv` first if
  you're nervous (or just commit it to a dotfiles repo).
- To rebalance your whole CSV after adding a lot of words, run
  `chordgen gen`. Reserved rows survive the rebalance so the
  added chords stay put.
