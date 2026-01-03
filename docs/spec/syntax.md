# TahtLang Syntax Reference

## Overview

TahtLang uses a human-readable, line-based syntax designed for:
- **Vim-friendly editing**: Lines work with `dd`, `yy`, `p`
- **Version control**: Clean diffs, easy merges
- **Readability**: No JSON noise, just content

## Type Prefixes

All entity references use explicit type prefixes. This enables LSP autocomplete and prevents ambiguity.

| Prefix | Description | Example |
|--------|-------------|---------|
| `settings:` | Game settings | `settings:main` |
| `counter:` | Numeric values (0-100) | `counter:treasury` |
| `flag:` | Boolean states | `flag:war` |
| `character:` | Characters/NPCs | `character:advisor` |
| `card:` | Cards | `card:intro` |
| `variant:` | Character variants (emotions, poses) | `variant:angry` |
| `trigger:` | Trigger effects | `trigger:response` |

## Entity Definitions

Entities are defined at the top of the file, before cards.

```tahta
# Format: DisplayName (type:id, ...modifiers)

# Settings
Game Settings (settings:main)

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

## Card Structure

```tahta
Card Name (card:card-id)
    bearer: character:name (variant:emotion)
    require: conditions
    weight: N
    weight: N when conditions
    lockturn: N | once | dispose
    > Card text shown to player
    * Choice A: effects
    * Choice B: effects
```

### Card Properties

| Property | Required | Description |
|----------|----------|-------------|
| `bearer` | Yes | Character who shows this card |
| `require` | No | Conditions for card to appear |
| `weight` | No* | Selection probability in pool |
| `lockturn` | No | Turns before card can reappear |

*Cards without weight are `ring` cards (chain-only).

### Bearer Syntax

```tahta
bearer: character:advisor                    # Simple
bearer: character:advisor (variant:angry)    # With emotion
```

### Weight Syntax

```tahta
weight: 1.0                              # Always this weight
weight: 2.0 when counter:treasury < 30   # Conditional weight
weight: 0.5 when flag:war                # Multiple conditions ok
```

### Lockturn Values

| Value | Description |
|-------|-------------|
| `lockturn: 60` | Lock for 60 turns after showing |
| `lockturn: once` | Lock for rest of this reign |
| `lockturn: dispose` | Remove permanently after showing |

## Conditions

Used in `require:` and `weight: N when`.

```tahta
require: flag:war                    # Flag must be set
require: !flag:war                   # Flag must NOT be set
require: counter:treasury < 30       # Counter less than
require: counter:treasury > 70       # Counter greater than
require: counter:treasury = 50       # Counter equals exactly
require: flag:war, counter:army > 50 # Multiple (AND)
```

## Choice Effects (Commands)

After the colon in a choice:

### Counter Modification

```tahta
* Choice: counter:treasury 20       # Add 20
* Choice: counter:treasury -20      # Subtract 20
* Choice: counter:army 10?30        # Random between 10-30
* Choice: counter:army -20?-10      # Random between -20 and -10
* Choice: counter:army -5?10        # Random between -5 and +10
```

### Flag Modification

```tahta
* Choice: +flag:war                 # Set flag
* Choice: -flag:war                 # Remove flag
```

### Card Queuing

```tahta
* Choice: card:next                 # Queue card (shows next)
* Choice: card:event@5              # Schedule for 5 turns later
* Choice: card:a, card:b, card:c    # Queue multiple (in order)
```

### Branching

```tahta
* Choice: [card:_path_a, card:_path_b]   # First with passing require
```

The runtime picks the first card in the list whose `require` conditions pass.

### Triggers

```tahta
* Choice: trigger:response "The king nods."    # Show response text
* Choice: trigger:sound "sword.wav"            # Play sound
```

### Combined Effects

```tahta
* Raise taxes: counter:treasury 20, counter:popularity -15, +flag:high_tax
* Go to war: counter:army -10, +flag:war, card:_battle@3
```

## Ring Cards (Chain Cards)

Ring cards can only appear via queue/schedule, never from the random pool.

```tahta
Battle Start (card:_battle, ring)
    bearer: character:general
    require: flag:war
    > The battle begins!
    * Attack: [card:_victory, card:_defeat]
    * Retreat: -flag:war, counter:popularity -20

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
- Can have `require`, `weight`, `lockturn` (used for branch selection)

## Card Selection System

Four pools manage card availability:

```
┌─────────────────────────────────────────────────────────────────┐
│  WHAT TO SHOW (Priority Order)                                  │
├─────────────────────────────────────────────────────────────────┤
│  1. QUEUE                                                       │
│     └─ Immediate cards, added via `card:_id`                    │
│     └─ FIFO order: first added = first shown                    │
│                                                                 │
│  2. TIMEDEVENTS                                                 │
│     └─ Scheduled cards, added via `card:_id@N`                  │
│     └─ Counter decrements each turn                             │
│     └─ Moves to QUEUE when counter reaches 0                    │
│                                                                 │
│  3. POOL                                                        │
│     └─ All cards with `weight:` (non-ring)                      │
│     └─ Filtered by `require:` conditions                        │
│     └─ Selected randomly based on weights                       │
├─────────────────────────────────────────────────────────────────┤
│  WHAT CAN'T BE SHOWN                                            │
├─────────────────────────────────────────────────────────────────┤
│  4. LOCKTURN                                                    │
│     └─ Recently shown cards, temporarily unavailable            │
│     └─ Counter decrements each turn                             │
│     └─ Returns to POOL when counter reaches 0                   │
│     └─ `lockturn: once` → counter = ∞ (until reign ends)        │
│     └─ `lockturn: dispose` → never returns (deleted)            │
└─────────────────────────────────────────────────────────────────┘
```

### Turn Flow

```
Each turn:
  1. Decrement all TIMEDEVENTS counters
     → Move cards with counter=0 to QUEUE

  2. Decrement all LOCKTURN counters
     → Move cards with counter=0 back to POOL

  3. Select next card:
     → If QUEUE not empty: pop first card
     → Else: pick from POOL (weighted random, filtered by require)

  4. Show card, player makes choice

  5. Apply effects:
     → If card has lockturn: move to LOCKTURN pool
     → Process counter/flag changes
     → Queue/schedule any cards from choice
```

## Comments

```tahta
# This is a comment
# Comments start with # and extend to end of line
```

## Complete Example

```tahta
# === SETTINGS ===
Game Settings (settings:main)

# === COUNTERS ===
Treasury (counter:treasury, killer)
Army (counter:army, killer)
People (counter:people, killer)
Church (counter:church, killer)

# === FLAGS ===
Game Start (flag:start)
War Active (flag:war)

# === CHARACTERS ===
Advisor (character:advisor)
General (character:general)

# === CARDS ===

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
    bearer: character:advisor
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
    > We have lost...
    * Retreat: -flag:war, counter:army -20, counter:people -15
```
