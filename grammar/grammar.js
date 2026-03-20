// TahtaScript Tree-sitter Grammar
// ================================
// Line-oriented DSL - parsing is simpler line by line

module.exports = grammar({
  name: 'tahta',

  extras: $ => [/[ ]+/],  // Ignore spaces (but not tabs - they're significant)

  rules: {
    source_file: $ => repeat($._definition),

    _definition: $ => choice(
      $.import_statement,
      $.entity,
      $.comment,
      /\r?\n/
    ),

    // Import statement: import "path/to/file.tahta"
    import_statement: $ => seq(
      token(prec(10, 'import')),
      $.string,
      /\r?\n/
    ),

    // Top-level comment
    comment: $ => /#[^\r\n]*/,

    // Entity: header + indented body
    entity: $ => seq(
      $.entity_header,
      repeat($.body_line)
    ),

    entity_header: $ => seq(
      $.entity_name,
      '(',
      $.entity_type_spec,
      optional($.modifier_list),
      ')',
      /\r?\n/
    ),

    entity_name: $ => /[^(\r\n\t]+/,  // No tabs - entity names start at column 0

    entity_type_spec: $ => choice(
      seq('settings', ':', $.identifier),
      seq('counter', ':', $.identifier),
      seq('flag', ':', $.identifier),
      seq('variant', ':', $.identifier),
      seq('character', ':', $.identifier),
      seq('card', ':', $.identifier)
    ),

    modifier_list: $ => repeat1(seq(',', $.modifier)),
    modifier: $ => choice('killer', 'keep', 'ring'),

    // Indented body line
    body_line: $ => seq(
      /\t/,
      choice(
        $.property,
        $.card_text,
        $.choice,
        $.inline_comment
      ),
      /\r?\n/
    ),

    inline_comment: $ => /#[^\r\n]*/,

    // Properties
    property: $ => choice(
      // Settings properties
      seq('description', ':', $.string),
      seq('starting_flags', ':', $.flag_ref_list),
      seq('game_over_on_zero', ':', $.boolean),
      seq('game_over_on_max', ':', $.boolean),
      // Counter properties
      seq('start', ':', $.integer),
      seq('icon', ':', $.rest_of_line),
      seq('color', ':', $.string),
      // Virtual counter properties
      seq('source', ':', $.reference_list),
      seq('aggregate', ':', $.aggregate_type),
      seq('track', ':', $.track_type),
      // Flag properties
      seq('bind', ':', $.character_ref),
      // Character/Variant properties
      seq('prompt', ':', $.string),
      // Card properties
      seq('bearer', ':', $.bearer_value),
      seq('require', ':', $.condition_list),
      seq('weight', ':', $.weight_value),
      seq('lockturn', ':', $.lockturn_value)
    ),

    // Virtual counter types
    aggregate_type: $ => choice('average', 'sum', 'min', 'max'),
    track_type: $ => choice('yes', 'no'),

    // Lockturn: integer or special values
    lockturn_value: $ => choice($.integer, 'once', 'dispose'),

    // Card-specific
    bearer_value: $ => seq(
      $.character_ref,
      optional(seq('(', $.variant_ref, ')'))
    ),

    weight_value: $ => seq(
      $.number,
      optional(seq('when', $.condition))
    ),

    card_text: $ => seq('>', $.rest_of_line),

    choice: $ => seq(
      '*',
      optional($.choice_label),
      ':',
      optional($.command_list)
    ),

    choice_label: $ => /[^:\r\n]+/,

    // Conditions
    condition_list: $ => sep1($.condition, ','),
    condition: $ => choice($.flag_condition, $.counter_condition),
    flag_condition: $ => seq(optional('!'), $.flag_ref),
    counter_condition: $ => seq($.counter_ref, choice('<=', '>=', '<', '>', '='), $.integer),

    // Commands
    command_list: $ => sep1($.command, ','),
    command: $ => choice(
      $.counter_mod,
      $.flag_add,
      $.flag_remove,
      $.card_branch,
      $.card_timed,
      $.card_queue,
      $.trigger_cmd
    ),

    // Counter modification: counter:x N (value includes sign)
    counter_mod: $ => seq('counter', ':', $.identifier, $.signed_value_or_range),

    signed_value_or_range: $ => choice(
      prec(2, $.signed_range_value),
      prec(1, $.signed_integer)
    ),
    signed_integer: $ => /-?\d+/,
    signed_range_value: $ => seq($.signed_integer, '?', $.signed_integer),

    // Flag commands
    flag_add: $ => seq('+', 'flag', ':', $.identifier),
    flag_remove: $ => seq('-', 'flag', ':', $.identifier),

    // Card commands
    card_queue: $ => prec(1, seq('card', ':', $.identifier)),
    card_timed: $ => prec(2, seq('card', ':', $.identifier, '@', $.integer)),
    card_branch: $ => seq('[', sep1($.card_ref, ','), ']'),

    // Trigger commands (response text, sound effects, etc.)
    trigger_cmd: $ => seq('trigger', ':', $.trigger_type, $.string),
    trigger_type: $ => choice('response', 'sound'),

    // References
    counter_ref: $ => seq('counter', ':', $.identifier),
    flag_ref: $ => seq('flag', ':', $.identifier),
    character_ref: $ => seq('character', ':', $.identifier),
    variant_ref: $ => seq('variant', ':', $.identifier),
    card_ref: $ => seq('card', ':', $.identifier),

    // Reference lists (for source: property)
    reference_list: $ => seq('[', sep1($.reference, ','), ']'),
    reference: $ => choice($.counter_ref, $.character_ref),

    flag_ref_list: $ => seq('[', sep1($.flag_ref, ','), ']'),

    // Primitives
    identifier: $ => /[a-zA-Z_][a-zA-Z0-9_-]*/,
    integer: $ => /\d+/,
    number: $ => /\d+(\.\d+)?/,
    string: $ => /"[^"]*"/,
    boolean: $ => choice('true', 'false'),
    rest_of_line: $ => /[^\r\n]+/,
  }
});

// Helper: comma-separated list with at least 1 element
function sep1(rule, separator) {
  return seq(rule, repeat(seq(separator, rule)));
}
