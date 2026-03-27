# TahtLang Syntax Reference

## Overview

TahtLang uses a human-readable, line-based syntax designed for:
- **Vim-friendly editing**: Lines work with `dd`, `yy`, `p`
- **Version control**: Clean diffs, easy merges
- **Readability**: No JSON noise, just content

## Type Prefixes

All entity references use explicit type prefixes. This enables
LSP autocomplete and prevents ambiguity.

| Prefix | Description | Example |
|--------|-------------|---------|
| `settings:` | Game settings | `settings:main` |
| `counter:` | Numeric values (0-100) | `counter:treasury` |
| `flag:` | Boolean states | `flag:war` |
| `character:` | Characters/NPCs | `character:advisor` |
| `card:` | Cards | `card:intro` |
| `variant:` | Character variants (emotions) | `variant:angry` |
| `trigger:` | Trigger effects | `trigger:response` |

## Entity Definitions

Entities are defined at the top of the file, before cards.

```taht
# Format: DisplayName (type:id, ...modifiers)

# Settings
Game Settings (settings:main)
    starting_flags: [flag:start]

# Counters
Treasury (counter:treasury, killer)
Army (counter:army, killer)
Popularity (counter:popularity)

# Flags
War Active (flag:war)
Winter (flag:winter, keep)

# Variants
Angry (variant:angry)
Happy (variant:happy)

# Characters
Advisor (character:advisor)
General (character:general)
```

### Entity Modifiers

| Modifier | Applies To | Description |
|----------|-----------|-------------|
| `killer` | counter | Game over when value hits 0 or 100 |
| `keep` | counter, flag | Persists across reigns (king deaths) |
| `ring` | card | Chain-only card, never in random pool |

### Settings Properties

| Property | Type | Description |
|----------|------|-------------|
| `starting_flags` | flag list | Flags set at game start |
| `game_over_on_zero` | bool | End game when killer counter hits 0 (default: true) |
| `game_over_on_max` | bool | End game when killer counter hits 100 (default: true) |

### Counter Properties

| Property | Type | Description |
|----------|------|-------------|
| `> N` | int | Starting value (default: 50) |
| `icon` | string | Display icon or label |
| `color` | string | Display color |
| `source` | reference list | Source counters/characters (virtual) |
| `aggregate` | average/sum/min/max | Aggregation type (virtual) |
| `track` | yes/no | Track type (virtual) |

### Virtual Counters

Counters that derive their value from other counters or characters:

```taht
# Aggregate: average of multiple counters
Overall (counter:overall)
    source: [counter:treasury, counter:army, counter:people]
    aggregate: average

# Track: count yes/no responses per character
Merchant Approval (counter:merchant_yes)
    source: [character:merchant]
    track: yes
```

### Flag Properties

| Property | Type | Description |
|----------|------|-------------|
| `bind` | character ref | Bind flag to a character |

### Character and Variant Properties

| Property | Type | Description |
|----------|------|-------------|
| `prompt` | string | AI generation prompt |
| `meta.*` | any | Free-form metadata (characters only) |

## Card Structure

```taht
Card Name (card:card-id)
    bearer: character:name (variant:emotion)
    require: conditions
    weight: N
    weight: N when conditions
    lockturn: N | once | dispose
    meta.key: value
    > Card text shown to player
    * Choice A: effects
    * Choice B: effects
```

### Card Properties

| Property | Required | Description |
|----------|----------|-------------|
| `bearer` | No | Character who presents this card |
| `require` | No | Conditions for card to appear |
| `weight` | No* | Selection probability in pool |
| `lockturn` | No | Cooldown after card is shown |
| `meta.*` | No | Free-form metadata for runtime |

*Cards without weight are `ring` cards (chain-only).

### Bearer Syntax

```taht
bearer: character:advisor                    # Simple
bearer: character:advisor (variant:angry)    # With emotion
```

Bearer is optional. Cards without a bearer are event/narrator cards
(e.g. "Spring has arrived", game over scenes).

### Weight Syntax

```taht
weight: 1.0                              # Always this weight
weight: 2.0 when counter:treasury < 30   # Conditional weight
weight: 0.5 when flag:war                # Flag condition
```

Multiple weight lines are additive. A card with:
```taht
weight: 1.0
weight: 2.0 when counter:treasury < 30
```
has weight 1.0 normally, and 3.0 when treasury is below 30.

### Lockturn Values

| Value | Description |
|-------|-------------|
| `lockturn: 60` | Lock for 60 turns after showing |
| `lockturn: once` | Lock for rest of this reign |
| `lockturn: dispose` | Remove permanently after showing |

### Metadata

Cards and characters support free-form `meta.*` properties.
TahtLang does not validate these — they are passed through to
JSON output for your runtime to interpret.

```taht
Advisor (character:advisor)
    meta.portrait: advisor_portrait.png
    meta.voice: deep

Empty Vault (card:_go_vault, ring)
    meta.image: empty_vault.png
    meta.mood: dark
    meta.sound: vault_echo.ogg
    > The royal vaults echo with emptiness.
    * ...
```

JSON output:
```json
{
  "meta": {
    "image": "empty_vault.png",
    "mood": "dark",
    "sound": "vault_echo.ogg"
  }
}
```

## Conditions

Used in `require:` and `weight: N when`.
Multiple conditions are combined with AND.

```taht
require: flag:war                    # Flag must be set
require: !flag:war                   # Flag must NOT be set
require: counter:treasury < 30       # Counter less than
require: counter:treasury > 70       # Counter greater than
require: counter:treasury <= 50      # Less than or equal
require: counter:treasury >= 50      # Greater than or equal
require: counter:treasury = 50       # Equals exactly
require: flag:war, counter:army > 50 # Multiple (AND)
```

## Choice Effects (Commands)

After the colon in a choice line:

### Counter Modification

```taht
* Choice: counter:treasury 20       # Add 20
* Choice: counter:treasury -20      # Subtract 20
* Choice: counter:army 10?30        # Random between 10-30
* Choice: counter:army -20?-10      # Random between -20 and -10
* Choice: counter:army -5?10        # Random between -5 and +10
```

### Flag Modification

```taht
* Choice: +flag:war                 # Set flag
* Choice: -flag:war                 # Clear flag
```

### Card Queuing

```taht
* Choice: card:next                 # Queue (shows next turn)
* Choice: card:event@5              # Schedule for 5 turns later
* Choice: card:a, card:b, card:c    # Queue multiple (in order)
```

### Branching

```taht
* Choice: [card:_path_a, card:_path_b]   # First with passing require
```

The runtime picks the first card in the list whose `require`
conditions pass.

### Triggers

```taht
* Choice: trigger:response "The king nods."
* Choice: trigger:sound "sword.wav"
```

### Combined Effects

```taht
* Raise taxes: counter:treasury 20, counter:people -15, +flag:high_tax
* Go to war: counter:army -10, +flag:war, card:_battle@3
```

## Ring Cards (Chain Cards)

Ring cards can only appear via queue/schedule, never from the
random pool.

```taht
Battle (card:_battle, ring)
    bearer: character:general
    require: flag:war
    > The battle begins!
    * Attack: [card:_victory, card:_defeat]
    * Retreat: -flag:war, counter:people -20

Victory (card:_victory, ring)
    bearer: character:general
    require: counter:army > 30
    > We have won!
    * Celebrate: -flag:war, counter:treasury 50

Defeat (card:_defeat, ring)
    bearer: character:general
    require: counter:army <= 30
    > We have lost...
    * Accept: -flag:war, counter:army -30
```

**Rules:**
- ID must start with `_` prefix
- Must have `ring` modifier
- Can have `require`, `weight`, `lockturn`

## Imports

Split large games across files:

```taht
import "characters.taht"
import "story/chapter1.taht"
import "events/random.taht"
```

Import paths are relative to the importing file.

## Card Selection (Runtime)

Priority order:
1. **Scheduled cards**: Cards whose `card:id@N` delay has elapsed
2. **Queued cards**: Cards added via `card:id` (FIFO)
3. **Random pool**: Weighted random selection from eligible cards

Eligibility for random pool:
- Not a `ring` card
- Not locked (lockturn cooldown)
- All `require` conditions pass
- Total weight > 0

## Comments

```taht
# This is a comment
# Comments start with # and extend to end of line
```

## Complete Example

```taht
# Settings
Game Settings (settings:main)
    starting_flags: [flag:start]

# Counters
Treasury (counter:treasury, killer)
    > 50
    icon: coin
Army (counter:army, killer)
    > 50
People (counter:people, killer)
    > 50
Church (counter:church, killer)
    > 50

# Flags
Game Start (flag:start)
War Active (flag:war)

# Variants
Angry (variant:angry)
Worried (variant:worried)

# Characters
Advisor (character:advisor)
    meta.portrait: advisor.png
General (character:general)

# Cards

Welcome (card:welcome)
    bearer: character:advisor
    weight: 100
    require: flag:start
    lockturn: dispose
    > Welcome, Your Majesty!
    * Begin: -flag:start, card:_tutorial

Tutorial (card:_tutorial, ring)
    bearer: character:advisor
    > Swipe left or right to make decisions.
    * I understand:

Tax Proposal (card:tax)
    bearer: character:advisor (variant:worried)
    weight: 1.0
    weight: 2.0 when counter:treasury < 30
    lockturn: 10
    > The treasury needs funds.
    * Raise taxes: counter:treasury 20, counter:people -15
    * Cut spending: counter:treasury 10, counter:army -10
    * Do nothing: counter:treasury -5

War Declaration (card:war)
    bearer: character:general
    weight: 0.5
    require: !flag:war, counter:army > 40
    lockturn: 30
    > Enemies threaten our borders!
    * Prepare for war: +flag:war, card:_battle@5
    * Seek peace: counter:treasury -30

Battle (card:_battle, ring)
    bearer: character:general
    require: flag:war
    meta.image: battlefield.png
    > The battle rages on!
    * Attack: counter:army -15, [card:_victory, card:_defeat]
    * Defend: counter:army -5, card:_battle@3

Victory (card:_victory, ring)
    bearer: character:general
    require: counter:army > 25
    > We have won!
    * Celebrate: -flag:war, counter:people 20, counter:treasury 30

Defeat (card:_defeat, ring)
    bearer: character:general
    require: counter:army <= 25
    meta.mood: dark
    > We have lost...
    * Retreat: -flag:war, counter:army -20, counter:people -15
```
