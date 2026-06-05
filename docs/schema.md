# Config

## Properties

- <a id="properties/gen"></a>**`gen`**: Refer to *[#/$defs/GenOptions](#%24defs/GenOptions)*. Default:

  ```yaml
  file: ~/.config/chordgen/chords.csv
  keyboard:
    directional:
      custom_layout:
      - _X__X__X__X__X__X__X__X_
      - X_XX_XX_XX_XX_XX_XX_XX_X
      - _X__X__X__X__X__X__X__X_
      - _X__X_
      - X_XX_X
      - _X__X_
      - _X__X_
      - X_XX_X
      - _X__X_
      custom_layout_name: custom
      directional_change_penalty: 2
      effort_map:
      - '040030020020'
      - '695594493493'
      - '030020010010'
      - '030'
      - '192'
      - '040'
      - '030'
      - '192'
      - '040'
      layout: charachorder
    standard:
      custom_layout:
      - _qwertyuiop_
      - _asdfghjkl;_
      - _zxcvbnm,./_
      - ____
      custom_layout_name: custom
      effort_map:
      - '965446'
      - '732116'
      - '865536'
      - '43'
      layout: qwerty
      same_column_chord_penalty: 2
      same_row_chord_penalty: 2
      scissor_penalty: 3
    type: standard
  alts:
    adjective:
      enabled: true
      forms:
      - comparative
      - superlative
    adverb:
      enabled: true
      forms: []
    noun:
      enabled: true
      forms:
      - plural
    overwrite: false
    verb:
      enabled: true
      forms:
      - 3sg
      - past
      - gerund
  assignment:
    frequency_exponent: 1.0
    min_frequency_weight: 1.0
    priority_tiers: []
    unmatched_penalty: 10000.0
  min_word_length: 3
  min_chord_length: 0
  ```

- <a id="properties/output"></a>**`output`**: Refer to *[#/$defs/OutputOptions](#%24defs/OutputOptions)*. Default:

  ```yaml
  formats:
  - qmk
  - zmk
  - charachorder
  - kanata
  - training
  qmk:
    alt1_keys:
    - KC_CHORD_ALT1
    alt2_keys:
    - KC_CHORD_ALT2
    alt3_keys:
    - KC_CHORD_ALT1
    - KC_CHORD_ALT2
    chord_keys:
    - KC_CHORD
    file: ~/.config/chordgen/qmk_chords.def
    key_codes:
      ;: KC_SFT_SEMI
      A: KC_SFT_A
      D: KC_GUI_D
      F: KC_CTL_F
      J: KC_CTL_J
      K: KC_GUI_K
      L: KC_ALT_L
      S: KC_ALT_S
    shifted_chord_keys:
    - KC_CHORD
    - KC_CHORD_SFT
  zmk:
    alt1_keys:
    - '!'
    alt2_keys:
    - '@'
    alt3_keys:
    - '!'
    - '@'
    chord_keys:
    - $
    chord_timeout: 100
    chords_file: ~/.config/chordgen/zmk_chords.dtsi
    key_positions:
    - _qwertyuiop_
    - _asdfghjkl;_
    - _zxcvbnm,./_
    - _!@#$_
    limit: 200
    macros_file: ~/.config/chordgen/zmk_macros.dtsi
    shifted_chord_keys:
    - $
    - '#'
  charachorder:
    file: ~/.config/chordgen/charachorder_chords.json
  kanata:
    alt1_keys:
    - lalt
    alt2_keys:
    - spc
    alt3_keys:
    - lalt
    - spc
    chord_keys:
    - prtsc
    chord_timeout: 100
    file: ~/.config/chordgen/kanata_chords.kbd
    key_mapping: {}
    limit: 0
    shifted_chord_keys:
    - prtsc
    - ralt
  training:
    file: ~/.config/chordgen/training.txt
  ```

- <a id="properties/train"></a>**`train`**: Refer to *[#/$defs/TrainOptions](#%24defs/TrainOptions)*. Default:

  ```yaml
  show_words: 10
  new_words_per_day: 20
  reviews_per_day: 200
  leech_threshold: 8
  mastery_threshold: 3
  relearn_steps: 3
  target_retention: 0.9
  slow_wpm_fraction: 0.7
  slow_min_samples: 20
  ```

- <a id="properties/drill"></a>**`drill`**: Refer to *[#/$defs/DrillOptions](#%24defs/DrillOptions)*. Default:

  ```yaml
  show_words: 10
  mode: time
  count: 25
  time_seconds: 30
  ```

- <a id="properties/book"></a>**`book`**: Refer to *[#/$defs/BookOptions](#%24defs/BookOptions)*. Default:

  ```yaml
  wpm_window_seconds: 30
  max_width: 80
  ```

- <a id="properties/theme"></a>**`theme`** *(string)*: Textual theme used by the train and drill TUIs. Updated automatically when you change the theme via the in-app command palette (Ctrl+P). Default: `"textual-dark"`.
## Definitions

- <a id="%24defs/AdjectiveAltOptions"></a>**`AdjectiveAltOptions`** *(object)*
  - <a id="%24defs/AdjectiveAltOptions/properties/enabled"></a>**`enabled`** *(boolean)*: Default: `true`.
  - <a id="%24defs/AdjectiveAltOptions/properties/forms"></a>**`forms`** *(array)*: Adjective forms to fill alt1..alt3 with, in order. Length must be at most 3. Default: `["comparative", "superlative"]`.
    - <a id="%24defs/AdjectiveAltOptions/properties/forms/items"></a>**Items** *(string)*: Must be one of: "comparative" or "superlative".
- <a id="%24defs/AdverbAltOptions"></a>**`AdverbAltOptions`** *(object)*
  - <a id="%24defs/AdverbAltOptions/properties/enabled"></a>**`enabled`** *(boolean)*: Default: `true`.
  - <a id="%24defs/AdverbAltOptions/properties/forms"></a>**`forms`** *(array)*: Adverb forms to fill alt1..alt3 with, in order. Length must be at most 3. Default: `[]`.
    - <a id="%24defs/AdverbAltOptions/properties/forms/items"></a>**Items** *(string)*: Must be one of: "comparative" or "superlative".
- <a id="%24defs/AltOptions"></a>**`AltOptions`** *(object)*
  - <a id="%24defs/AltOptions/properties/overwrite"></a>**`overwrite`** *(boolean)*: Overwrite existing alt1/alt2/alt3 values in chords.csv. By default, non-empty alt slots are preserved. Default: `false`.
  - <a id="%24defs/AltOptions/properties/verb"></a>**`verb`**: Refer to *[#/$defs/VerbAltOptions](#%24defs/VerbAltOptions)*. Default:

    ```yaml
    enabled: true
    forms:
    - 3sg
    - past
    - gerund
    ```

  - <a id="%24defs/AltOptions/properties/noun"></a>**`noun`**: Refer to *[#/$defs/NounAltOptions](#%24defs/NounAltOptions)*. Default:

    ```yaml
    enabled: true
    forms:
    - plural
    ```

  - <a id="%24defs/AltOptions/properties/adjective"></a>**`adjective`**: Refer to *[#/$defs/AdjectiveAltOptions](#%24defs/AdjectiveAltOptions)*. Default:

    ```yaml
    enabled: true
    forms:
    - comparative
    - superlative
    ```

  - <a id="%24defs/AltOptions/properties/adverb"></a>**`adverb`**: Refer to *[#/$defs/AdverbAltOptions](#%24defs/AdverbAltOptions)*. Default:

    ```yaml
    enabled: true
    forms: []
    ```

- <a id="%24defs/AssignmentOptions"></a>**`AssignmentOptions`** *(object)*
  - <a id="%24defs/AssignmentOptions/properties/min_frequency_weight"></a>**`min_frequency_weight`** *(number)*: Floor for the weight applied to words missing a frequency value. Treats them as low-priority but still eligible. Default: `1.0`.
  - <a id="%24defs/AssignmentOptions/properties/unmatched_penalty"></a>**`unmatched_penalty`** *(number)*: Cost charged per word that ends up without a chord. Acts as a soft constraint in the optimal matcher: if recovering a word would cost more than this, leaving it unmatched is allowed. Default: `10000.0`.
  - <a id="%24defs/AssignmentOptions/properties/frequency_exponent"></a>**`frequency_exponent`** *(number)*: Exponent applied to each word's frequency weight before it multiplies the chord score. The default 1.0 reproduces the original linear cost model. Values > 1 (try 2.0 or 3.0) make frequent words dominate the cost so the matcher won't trade a common word's short chord to a rare word that happens to improve the global sum slightly. Must be > 0. Default: `1.0`.
  - <a id="%24defs/AssignmentOptions/properties/priority_tiers"></a>**`priority_tiers`** *(array)*: Cumulative frequency-rank cutoffs for tiered assignment. The pool (already in descending-frequency order) is split at each cutoff, then each tier is solved by the optimal matcher in order, with previous tiers' chord keys reserved out. Default [] runs a single global pass. Example [500, 1000] runs three passes: top 500 -> next 500 -> rest. Cutoffs must be strictly increasing; values >= len(pool) are clamped. Default: `[]`.
    - <a id="%24defs/AssignmentOptions/properties/priority_tiers/items"></a>**Items** *(integer)*
- <a id="%24defs/BookOptions"></a>**`BookOptions`** *(object)*
  - <a id="%24defs/BookOptions/properties/wpm_window_seconds"></a>**`wpm_window_seconds`** *(integer)*: Sliding window (in seconds) over which the running WPM is computed in book mode. Default: `30`.
  - <a id="%24defs/BookOptions/properties/max_width"></a>**`max_width`** *(integer)*: Maximum width (in characters) of the rendered text block in book mode. Long paragraphs are wrapped to this width. Default: `80`.
- <a id="%24defs/CharaChorderOutput"></a>**`CharaChorderOutput`** *(object)*
  - <a id="%24defs/CharaChorderOutput/properties/file"></a>**`file`** *(string, format: path)*: Default: `"~/.config/chordgen/charachorder_chords.json"`.
- <a id="%24defs/DirectionalKeyboardOptions"></a>**`DirectionalKeyboardOptions`** *(object)*
  - <a id="%24defs/DirectionalKeyboardOptions/properties/layout"></a>**`layout`** *(string)*: Must be one of: "charachorder", "stained", "svalboard_qwerty", or "custom". Default: `"charachorder"`.
  - <a id="%24defs/DirectionalKeyboardOptions/properties/directional_change_penalty"></a>**`directional_change_penalty`** *(integer)*: A penalty to add when chords have different directions per finger on the same hand. Can be set to -1 to disable this type of chord. Default: `2`.
  - <a id="%24defs/DirectionalKeyboardOptions/properties/custom_layout"></a>**`custom_layout`** *(array)*: Default: `["_X__X__X__X__X__X__X__X_", "X_XX_XX_XX_XX_XX_XX_XX_X", "_X__X__X__X__X__X__X__X_", "_X__X_", "X_XX_X", "_X__X_", "_X__X_", "X_XX_X", "_X__X_"]`.
    - <a id="%24defs/DirectionalKeyboardOptions/properties/custom_layout/items"></a>**Items** *(string)*
  - <a id="%24defs/DirectionalKeyboardOptions/properties/custom_layout_name"></a>**`custom_layout_name`** *(string)*: Display name used for a custom layout in places like the drill score leaderboard. Only meaningful when layout='custom'. Default: `"custom"`.
  - <a id="%24defs/DirectionalKeyboardOptions/properties/effort_map"></a>**`effort_map`** *(array)*: Default: `["040030020020", "695594493493", "030020010010", "030", "192", "040", "030", "192", "040"]`.
    - <a id="%24defs/DirectionalKeyboardOptions/properties/effort_map/items"></a>**Items** *(string)*
- <a id="%24defs/DrillOptions"></a>**`DrillOptions`** *(object)*
  - <a id="%24defs/DrillOptions/properties/show_words"></a>**`show_words`** *(integer)*: Number of words shown on screen at once during a drill. Default: `10`.
  - <a id="%24defs/DrillOptions/properties/mode"></a>**`mode`** *(string)*: How a drill session ends: 'count' stops after a fixed number of words, 'time' stops when the timer runs out. Must be one of: "count" or "time". Default: `"time"`.
  - <a id="%24defs/DrillOptions/properties/count"></a>**`count`** *(integer)*: Number of words drilled when ``mode = count``. Ignored when ``mode = time``. Default: `25`.
  - <a id="%24defs/DrillOptions/properties/time_seconds"></a>**`time_seconds`** *(integer)*: Duration of the drill in seconds when ``mode = time``. Ignored when ``mode = count``. Default: `30`.
- <a id="%24defs/GenOptions"></a>**`GenOptions`** *(object)*
  - <a id="%24defs/GenOptions/properties/file"></a>**`file`** *(string, format: path)*: Default: `"~/.config/chordgen/chords.csv"`.
  - <a id="%24defs/GenOptions/properties/keyboard"></a>**`keyboard`**: Refer to *[#/$defs/KeyboardOptions](#%24defs/KeyboardOptions)*. Default:

    ```yaml
    type: standard
    standard:
      custom_layout:
      - _qwertyuiop_
      - _asdfghjkl;_
      - _zxcvbnm,./_
      - ____
      custom_layout_name: custom
      effort_map:
      - '965446'
      - '732116'
      - '865536'
      - '43'
      layout: qwerty
      same_column_chord_penalty: 2
      same_row_chord_penalty: 2
      scissor_penalty: 3
    directional:
      custom_layout:
      - _X__X__X__X__X__X__X__X_
      - X_XX_XX_XX_XX_XX_XX_XX_X
      - _X__X__X__X__X__X__X__X_
      - _X__X_
      - X_XX_X
      - _X__X_
      - _X__X_
      - X_XX_X
      - _X__X_
      custom_layout_name: custom
      directional_change_penalty: 2
      effort_map:
      - '040030020020'
      - '695594493493'
      - '030020010010'
      - '030'
      - '192'
      - '040'
      - '030'
      - '192'
      - '040'
      layout: charachorder
    ```

  - <a id="%24defs/GenOptions/properties/alts"></a>**`alts`**: Refer to *[#/$defs/AltOptions](#%24defs/AltOptions)*. Default:

    ```yaml
    overwrite: false
    verb:
      enabled: true
      forms:
      - 3sg
      - past
      - gerund
    noun:
      enabled: true
      forms:
      - plural
    adjective:
      enabled: true
      forms:
      - comparative
      - superlative
    adverb:
      enabled: true
      forms: []
    ```

  - <a id="%24defs/GenOptions/properties/assignment"></a>**`assignment`**: Refer to *[#/$defs/AssignmentOptions](#%24defs/AssignmentOptions)*. Default:

    ```yaml
    min_frequency_weight: 1.0
    unmatched_penalty: 10000.0
    frequency_exponent: 1.0
    priority_tiers: []
    ```

  - <a id="%24defs/GenOptions/properties/min_word_length"></a>**`min_word_length`** *(integer)*: Default: `3`.
  - <a id="%24defs/GenOptions/properties/min_chord_length"></a>**`min_chord_length`** *(integer)*: The minimum length a chord, setting this to 2 and disabling the chord key is a way to avoid needing a chord key. This works well on CharaChorder, but you will need to lower the chord timeout to avoid missfires on other keyboards. Default: `0`.
- <a id="%24defs/KanataOutput"></a>**`KanataOutput`** *(object)*
  - <a id="%24defs/KanataOutput/properties/file"></a>**`file`** *(string, format: path)*: Default: `"~/.config/chordgen/kanata_chords.kbd"`.
  - <a id="%24defs/KanataOutput/properties/chord_keys"></a>**`chord_keys`** *(array)*: Default: `["prtsc"]`.
    - <a id="%24defs/KanataOutput/properties/chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/KanataOutput/properties/shifted_chord_keys"></a>**`shifted_chord_keys`** *(array)*: Default: `["prtsc", "ralt"]`.
    - <a id="%24defs/KanataOutput/properties/shifted_chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/KanataOutput/properties/alt1_keys"></a>**`alt1_keys`** *(array)*: Default: `["lalt"]`.
    - <a id="%24defs/KanataOutput/properties/alt1_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/KanataOutput/properties/alt2_keys"></a>**`alt2_keys`** *(array)*: Default: `["spc"]`.
    - <a id="%24defs/KanataOutput/properties/alt2_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/KanataOutput/properties/alt3_keys"></a>**`alt3_keys`** *(array)*: Default: `["lalt", "spc"]`.
    - <a id="%24defs/KanataOutput/properties/alt3_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/KanataOutput/properties/limit"></a>**`limit`** *(integer)*: Default: `0`.
  - <a id="%24defs/KanataOutput/properties/chord_timeout"></a>**`chord_timeout`** *(integer)*: Default: `100`.
  - <a id="%24defs/KanataOutput/properties/key_mapping"></a>**`key_mapping`** *(object)*: Since Kanata combos are based in the layout in defsrc (probably qwerty) you will need to remap the letters if you are using a custom layout eg. 'a': 'b'. Can contain additional properties. Default: `{}`.
    - <a id="%24defs/KanataOutput/properties/key_mapping/additionalProperties"></a>**Additional properties** *(string)*
- <a id="%24defs/KeyboardOptions"></a>**`KeyboardOptions`** *(object)*
  - <a id="%24defs/KeyboardOptions/properties/type"></a>**`type`** *(string)*: Must be one of: "standard" or "directional". Default: `"standard"`.
  - <a id="%24defs/KeyboardOptions/properties/standard"></a>**`standard`**: Refer to *[#/$defs/StandardKeyboardOptions](#%24defs/StandardKeyboardOptions)*. Default:

    ```yaml
    layout: qwerty
    scissor_penalty: 3
    same_column_chord_penalty: 2
    same_row_chord_penalty: 2
    custom_layout:
    - _qwertyuiop_
    - _asdfghjkl;_
    - _zxcvbnm,./_
    - ____
    custom_layout_name: custom
    effort_map:
    - '965446'
    - '732116'
    - '865536'
    - '43'
    ```

  - <a id="%24defs/KeyboardOptions/properties/directional"></a>**`directional`**: Refer to *[#/$defs/DirectionalKeyboardOptions](#%24defs/DirectionalKeyboardOptions)*. Default:

    ```yaml
    layout: charachorder
    directional_change_penalty: 2
    custom_layout:
    - _X__X__X__X__X__X__X__X_
    - X_XX_XX_XX_XX_XX_XX_XX_X
    - _X__X__X__X__X__X__X__X_
    - _X__X_
    - X_XX_X
    - _X__X_
    - _X__X_
    - X_XX_X
    - _X__X_
    custom_layout_name: custom
    effort_map:
    - '040030020020'
    - '695594493493'
    - '030020010010'
    - '030'
    - '192'
    - '040'
    - '030'
    - '192'
    - '040'
    ```

- <a id="%24defs/NounAltOptions"></a>**`NounAltOptions`** *(object)*
  - <a id="%24defs/NounAltOptions/properties/enabled"></a>**`enabled`** *(boolean)*: Default: `true`.
  - <a id="%24defs/NounAltOptions/properties/forms"></a>**`forms`** *(array)*: Noun forms to fill alt1..alt3 with, in order. Length must be at most 3. Default: `["plural"]`.
    - <a id="%24defs/NounAltOptions/properties/forms/items"></a>**Items** *(string)*: Must be one of: "plural" or "singular".
- <a id="%24defs/OutputOptions"></a>**`OutputOptions`** *(object)*
  - <a id="%24defs/OutputOptions/properties/formats"></a>**`formats`** *(array)*: Default: `["qmk", "zmk", "charachorder", "kanata", "training"]`.
    - <a id="%24defs/OutputOptions/properties/formats/items"></a>**Items** *(string)*: Must be one of: "qmk", "zmk", "charachorder", "kanata", or "training".
  - <a id="%24defs/OutputOptions/properties/qmk"></a>**`qmk`**: Refer to *[#/$defs/QmkOutput](#%24defs/QmkOutput)*. Default:

    ```yaml
    file: ~/.config/chordgen/qmk_chords.def
    chord_keys:
    - KC_CHORD
    shifted_chord_keys:
    - KC_CHORD
    - KC_CHORD_SFT
    alt1_keys:
    - KC_CHORD_ALT1
    alt2_keys:
    - KC_CHORD_ALT2
    alt3_keys:
    - KC_CHORD_ALT1
    - KC_CHORD_ALT2
    key_codes:
      ;: KC_SFT_SEMI
      A: KC_SFT_A
      D: KC_GUI_D
      F: KC_CTL_F
      J: KC_CTL_J
      K: KC_GUI_K
      L: KC_ALT_L
      S: KC_ALT_S
    ```

  - <a id="%24defs/OutputOptions/properties/zmk"></a>**`zmk`**: Refer to *[#/$defs/ZmkOutput](#%24defs/ZmkOutput)*. Default:

    ```yaml
    chords_file: ~/.config/chordgen/zmk_chords.dtsi
    macros_file: ~/.config/chordgen/zmk_macros.dtsi
    chord_keys:
    - $
    shifted_chord_keys:
    - $
    - '#'
    alt1_keys:
    - '!'
    alt2_keys:
    - '@'
    alt3_keys:
    - '!'
    - '@'
    limit: 200
    chord_timeout: 100
    key_positions:
    - _qwertyuiop_
    - _asdfghjkl;_
    - _zxcvbnm,./_
    - _!@#$_
    ```

  - <a id="%24defs/OutputOptions/properties/charachorder"></a>**`charachorder`**: Refer to *[#/$defs/CharaChorderOutput](#%24defs/CharaChorderOutput)*. Default:

    ```yaml
    file: ~/.config/chordgen/charachorder_chords.json
    ```

  - <a id="%24defs/OutputOptions/properties/kanata"></a>**`kanata`**: Refer to *[#/$defs/KanataOutput](#%24defs/KanataOutput)*. Default:

    ```yaml
    file: ~/.config/chordgen/kanata_chords.kbd
    chord_keys:
    - prtsc
    shifted_chord_keys:
    - prtsc
    - ralt
    alt1_keys:
    - lalt
    alt2_keys:
    - spc
    alt3_keys:
    - lalt
    - spc
    limit: 0
    chord_timeout: 100
    key_mapping: {}
    ```

  - <a id="%24defs/OutputOptions/properties/training"></a>**`training`**: Refer to *[#/$defs/TrainingOutput](#%24defs/TrainingOutput)*. Default:

    ```yaml
    file: ~/.config/chordgen/training.txt
    ```

- <a id="%24defs/QmkOutput"></a>**`QmkOutput`** *(object)*
  - <a id="%24defs/QmkOutput/properties/file"></a>**`file`** *(string, format: path)*: Default: `"~/.config/chordgen/qmk_chords.def"`.
  - <a id="%24defs/QmkOutput/properties/chord_keys"></a>**`chord_keys`** *(array)*: Default: `["KC_CHORD"]`.
    - <a id="%24defs/QmkOutput/properties/chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/QmkOutput/properties/shifted_chord_keys"></a>**`shifted_chord_keys`** *(array)*: Default: `["KC_CHORD", "KC_CHORD_SFT"]`.
    - <a id="%24defs/QmkOutput/properties/shifted_chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/QmkOutput/properties/alt1_keys"></a>**`alt1_keys`** *(array)*: Default: `["KC_CHORD_ALT1"]`.
    - <a id="%24defs/QmkOutput/properties/alt1_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/QmkOutput/properties/alt2_keys"></a>**`alt2_keys`** *(array)*: Default: `["KC_CHORD_ALT2"]`.
    - <a id="%24defs/QmkOutput/properties/alt2_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/QmkOutput/properties/alt3_keys"></a>**`alt3_keys`** *(array)*: Default: `["KC_CHORD_ALT1", "KC_CHORD_ALT2"]`.
    - <a id="%24defs/QmkOutput/properties/alt3_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/QmkOutput/properties/key_codes"></a>**`key_codes`** *(object)*: Can contain additional properties. Default:

    ```yaml
    A: KC_SFT_A
    S: KC_ALT_S
    D: KC_GUI_D
    F: KC_CTL_F
    J: KC_CTL_J
    K: KC_GUI_K
    L: KC_ALT_L
    ;: KC_SFT_SEMI
    ```

    - <a id="%24defs/QmkOutput/properties/key_codes/additionalProperties"></a>**Additional properties** *(string)*
- <a id="%24defs/StandardKeyboardOptions"></a>**`StandardKeyboardOptions`** *(object)*
  - <a id="%24defs/StandardKeyboardOptions/properties/layout"></a>**`layout`** *(string)*: Must be one of: "qwerty", "colemak", "colemak_dh", "canary", "engram_2021", "engram_en", "enthium_v14", or "custom". Default: `"qwerty"`.
  - <a id="%24defs/StandardKeyboardOptions/properties/scissor_penalty"></a>**`scissor_penalty`** *(integer)*: A penalty to add when pressing keys on the top and bottom rows together. Can be set to -1 to disable this type of chord. Default: `3`.
  - <a id="%24defs/StandardKeyboardOptions/properties/same_column_chord_penalty"></a>**`same_column_chord_penalty`** *(integer)*: A penalty to add when pressing 2 keys and the same time with the same finger in the same column. Can be set to -1 to disable this type of chord. Default: `2`.
  - <a id="%24defs/StandardKeyboardOptions/properties/same_row_chord_penalty"></a>**`same_row_chord_penalty`** *(integer)*: A penalty to add when pressing 2 keys and the same time with the same finger in the same row. Can be set to -1 to disable this type of chord. Default: `2`.
  - <a id="%24defs/StandardKeyboardOptions/properties/custom_layout"></a>**`custom_layout`** *(array)*: Default: `["_qwertyuiop_", "_asdfghjkl;_", "_zxcvbnm,./_", "____"]`.
    - <a id="%24defs/StandardKeyboardOptions/properties/custom_layout/items"></a>**Items** *(string)*
  - <a id="%24defs/StandardKeyboardOptions/properties/custom_layout_name"></a>**`custom_layout_name`** *(string)*: Display name used for a custom layout in places like the drill score leaderboard. Only meaningful when layout='custom'. Default: `"custom"`.
  - <a id="%24defs/StandardKeyboardOptions/properties/effort_map"></a>**`effort_map`** *(array)*: Default: `["965446", "732116", "865536", "43"]`.
    - <a id="%24defs/StandardKeyboardOptions/properties/effort_map/items"></a>**Items** *(string)*
- <a id="%24defs/TrainOptions"></a>**`TrainOptions`** *(object)*
  - <a id="%24defs/TrainOptions/properties/show_words"></a>**`show_words`** *(integer)*: Number of words shown on screen at once during training. Default: `10`.
  - <a id="%24defs/TrainOptions/properties/new_words_per_day"></a>**`new_words_per_day`** *(integer)*: Maximum number of brand-new words introduced per calendar day, inspired by Anki's 'new cards per day' setting. Once the day's quota is exhausted no more new words are added until tomorrow. Default: `20`.
  - <a id="%24defs/TrainOptions/properties/reviews_per_day"></a>**`reviews_per_day`** *(integer)*: Maximum number of overdue / re-drilled review words surfaced per calendar day. Prevents a long absence from dumping the entire backlog at once. Default: `200`.
  - <a id="%24defs/TrainOptions/properties/leech_threshold"></a>**`leech_threshold`** *(integer)*: Number of lapses (Again ratings on a graduated word) after which a word is considered a 'leech' and called out in the session summary. Set to 0 to disable leech detection. Default: `8`.
  - <a id="%24defs/TrainOptions/properties/mastery_threshold"></a>**`mastery_threshold`** *(integer)*: Number of total FSRS reviews before a word is considered mastered and its chord is hidden during practice. If you make a mistake on a mastered word, its chord is revealed again for that attempt. Default: `3`.
  - <a id="%24defs/TrainOptions/properties/relearn_steps"></a>**`relearn_steps`** *(integer)*: Number of in-session correct repetitions a new or lapsed word must earn before it graduates and its FSRS state is updated. Higher values give more drilling on hard words but slow down session progress. Default: `3`.
  - <a id="%24defs/TrainOptions/properties/target_retention"></a>**`target_retention`** *(number)*: FSRS desired retention probability. The next review for each word is scheduled when its predicted recall falls to this value. Default: `0.9`.
  - <a id="%24defs/TrainOptions/properties/slow_wpm_fraction"></a>**`slow_wpm_fraction`** *(number)*: A correct word counts as 'slow' (FSRS hard) when its per-word WPM is below this fraction of the user's rolling median per-word WPM. Set to 0 to disable slow grading. Default: `0.7`.
  - <a id="%24defs/TrainOptions/properties/slow_min_samples"></a>**`slow_min_samples`** *(integer)*: Minimum number of recorded per-word WPM samples before slow grading activates. Until this is reached all correct words are graded 'good'. Default: `20`.
- <a id="%24defs/TrainingOutput"></a>**`TrainingOutput`** *(object)*
  - <a id="%24defs/TrainingOutput/properties/file"></a>**`file`** *(string, format: path)*: Default: `"~/.config/chordgen/training.txt"`.
- <a id="%24defs/VerbAltOptions"></a>**`VerbAltOptions`** *(object)*
  - <a id="%24defs/VerbAltOptions/properties/enabled"></a>**`enabled`** *(boolean)*: Default: `true`.
  - <a id="%24defs/VerbAltOptions/properties/forms"></a>**`forms`** *(array)*: Verb forms to fill alt1..alt3 with, in order. Length must be at most 3. Default: `["3sg", "past", "gerund"]`.
    - <a id="%24defs/VerbAltOptions/properties/forms/items"></a>**Items** *(string)*: Must be one of: "3sg", "past", "gerund", or "ppart".
- <a id="%24defs/ZmkOutput"></a>**`ZmkOutput`** *(object)*
  - <a id="%24defs/ZmkOutput/properties/chords_file"></a>**`chords_file`** *(string, format: path)*: Default: `"~/.config/chordgen/zmk_chords.dtsi"`.
  - <a id="%24defs/ZmkOutput/properties/macros_file"></a>**`macros_file`** *(string, format: path)*: Default: `"~/.config/chordgen/zmk_macros.dtsi"`.
  - <a id="%24defs/ZmkOutput/properties/chord_keys"></a>**`chord_keys`** *(array)*: Default: `["$"]`.
    - <a id="%24defs/ZmkOutput/properties/chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/ZmkOutput/properties/shifted_chord_keys"></a>**`shifted_chord_keys`** *(array)*: Default: `["$", "#"]`.
    - <a id="%24defs/ZmkOutput/properties/shifted_chord_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/ZmkOutput/properties/alt1_keys"></a>**`alt1_keys`** *(array)*: Default: `["!"]`.
    - <a id="%24defs/ZmkOutput/properties/alt1_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/ZmkOutput/properties/alt2_keys"></a>**`alt2_keys`** *(array)*: Default: `["@"]`.
    - <a id="%24defs/ZmkOutput/properties/alt2_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/ZmkOutput/properties/alt3_keys"></a>**`alt3_keys`** *(array)*: Default: `["!", "@"]`.
    - <a id="%24defs/ZmkOutput/properties/alt3_keys/items"></a>**Items** *(string)*
  - <a id="%24defs/ZmkOutput/properties/limit"></a>**`limit`** *(integer)*: Limit the number of chords outputted. It will vary depending on MCU, but I have found ZMK to be quite limited compared to QMK with the number or chords it can fit. Default: `200`.
  - <a id="%24defs/ZmkOutput/properties/chord_timeout"></a>**`chord_timeout`** *(integer)*: Default: `100`.
  - <a id="%24defs/ZmkOutput/properties/key_positions"></a>**`key_positions`** *(array)*: Should contain the same number of characters as keys on your keyboard. Use _ to ignore a key. Chord, shift, alt1, alt2 can be represented by shifted characters such as $#!@. Spaces will be ignored and can be used for formatting. Default: `["_qwertyuiop_", "_asdfghjkl;_", "_zxcvbnm,./_", "_!@#$_"]`.
    - <a id="%24defs/ZmkOutput/properties/key_positions/items"></a>**Items** *(string)*
