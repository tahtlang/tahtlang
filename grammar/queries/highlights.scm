; TahtLang Tree-sitter Syntax Highlighting
; =========================================
; For Neovim, Helix, Zed, and other tree-sitter editors

; Comments
(comment) @comment
(inline_comment) @comment

; Import statements
"import" @keyword.import
(import_statement (string) @string.special)

; Entity headers
(entity_name) @type
(entity_type_spec) @keyword

; Modifiers
(modifier) @keyword.modifier

; Type prefixes (counter:, flag:, etc.)
"counter" @type.builtin
"flag" @type.builtin
"character" @type.builtin
"variant" @type.builtin
"card" @type.builtin
"settings" @type.builtin
"trigger" @type.builtin

; Property names
"description" @property
"starting_flags" @property
"game_over_on_zero" @property
"game_over_on_max" @property
"start" @property
"icon" @property
"color" @property
"source" @property
"aggregate" @property
"track" @property
"bind" @property
"prompt" @property
"bearer" @property
"require" @property
"weight" @property
"lockturn" @property

; Virtual counter types
(aggregate_type) @constant
(track_type) @constant

; Lockturn special values
(lockturn_value "once" @constant)
(lockturn_value "dispose" @constant)

; Card text
(card_text ">" @punctuation.special)
(card_text (rest_of_line) @string)

; Choices
(choice "*" @punctuation.special)
(choice_label) @label

; Commands - counter modification
(counter_mod) @function

; Trigger commands
(trigger_cmd) @function
(trigger_type) @constant

; Flag commands
(flag_add "+" @operator)
(flag_remove "-" @operator)

; Branch syntax
(card_branch "[" @punctuation.bracket)
(card_branch "]" @punctuation.bracket)

; Condition operators
(counter_condition "<" @operator)
(counter_condition ">" @operator)
(counter_condition "=" @operator)
(flag_condition "!" @operator)
"when" @keyword.conditional

; Identifiers (entity IDs)
(identifier) @variable

; Literals
(integer) @number
(signed_integer) @number
(number) @number
(string) @string
(boolean) @boolean

; Range syntax
(signed_range_value "?" @operator)

; Timed card syntax
(card_timed "@" @operator)

; Punctuation
":" @punctuation.delimiter
"," @punctuation.delimiter
"(" @punctuation.bracket
")" @punctuation.bracket
"[" @punctuation.bracket
"]" @punctuation.bracket
