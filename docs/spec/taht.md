# .tahta File Format Specification

**Version:** 0.3.0 (Draft)
**Status:** Work in Progress

## Overview

`.tahta` is a complete game package format for Reigns-style card games. It's a ZIP archive containing all game data and assets needed to play.

The name comes from Turkish "tahta" meaning throne/board - fitting for a game about ruling decisions.

```
osmanli-sarayi.tahta (ZIP archive)
├── game.json               # SINGLE FILE - All game data
└── assets/
    ├── characters/
    │   └── fatma-kabatas/
    │       ├── base-portrait.png
    │       ├── panic.png
    │       └── happy.png
    ├── music/
    │   ├── tense.mp3
    │   └── happy.mp3
    ├── sfx/
    │   └── sword_clash.mp3
    └── ui/
        ├── background.png
        ├── splash.png
        └── icons/
            ├── hazine.png
            └── ordu.png
```

## Design Principles

1. **Self-contained**: Everything needed to play is in the package
2. **Portable**: Share a `.tahta` file, anyone can play
3. **Declarative**: Data describes *what*, engine decides *how*
4. **Extensible**: New commands/features don't break old content

---

## game.json Structure

**Single JSON file** containing all game data. Clean, validated, and portable.

```json
{
  "metadata": {
    "id": "osmanli-sarayi",
    "name": "Osmanlı Sarayı",
    "version": "1.0.0",
    "author": "Studio Name",
    "description": "16. yüzyıl Osmanlı sarayında padişah olarak hüküm sür",
    "status": "active",
    "splash_screen": {
      "default": "assets/ui/splash.png"
    },
    "ai_camera_angle": "Chest-to-head portrait, body slightly angled (3/4 view)",
    "ai_background": "solid black background",
    "ai_art_style": "4-bit, 16 color, EGA palette pixel art"
  },

  "settings": {
    "starting_metrics": {
      "hazine": 50,
      "ordu": 50,
      "halk": 50,
      "din": 50
    },
    "metric_range": [0, 100],
    "game_over_on_zero": true,
    "game_over_on_max": false
  },

  "theme": {
    "palettes": {
      "default": {
        "background": "#1a1a2e",
        "surface": "#16213e",
        "text": "#eee",
        "accent": "#d4af37"
      },
      "fire": {
        "background": "#2d1810",
        "text": "#fff",
        "accent": "#ff6b35"
      }
    }
  },

  "metrics": [
    {
      "id": "hazine",
      "name": "Hazine",
      "icon": "assets/ui/icons/hazine.png",
      "color": "#FFD700"
    },
    {
      "id": "ordu",
      "name": "Ordu",
      "icon": "assets/ui/icons/ordu.png",
      "color": "#8B0000"
    },
    {
      "id": "halk",
      "name": "Halk",
      "icon": "assets/ui/icons/halk.png",
      "color": "#228B22"
    },
    {
      "id": "din",
      "name": "Din",
      "icon": "assets/ui/icons/din.png",
      "color": "#4169E1"
    }
  ],

  "tags": [
    {
      "id": "economy",
      "name": "Economy",
      "type": "boolean",
      "color": "#4CAF50"
    },
    {
      "id": "nb_churches",
      "name": "Churches Built",
      "type": "counter",
      "color": "#9C27B0"
    }
  ],

  "emotions": [
    {
      "id": "neutral",
      "name": "Normal"
    },
    {
      "id": "panic",
      "name": "Panik",
      "music_mood": "tense"
    }
  ],

  "characters": [
    {
      "id": "fatma-kabatas",
      "name": "Fatma Kabataş",
      "role": "Saray Dadısı",
      "visual_prompt": "60-year-old woman, pearl earrings, grey-streaked hair...",
      "visual_analysis": {
        "clothing": "traditional Ottoman dress with ornate patterns",
        "facial_features": "sharp eyes, prominent nose, thin lips",
        "accessories": "pearl earrings, head covering",
        "age": "elderly, grey-streaked hair",
        "distinctive_traits": "stern expression, commanding presence"
      }
    }
  ],

  "cards": [
    {
      "id": "village-fire",
      "text": "Efendim! Köyde yangın var!",
      "character_id": "fatma-kabatas",
      "emotion_id": "panic",
      "tags": ["economy"],
      "prereqs": [],
      "weight": {
        "base": 1.0,
        "modifiers": []
      },
      "left": {
        "label": "Su taşıyın!",
        "commands": [
          {"_id": "cmd001", "key": "hazine", "type": "decr", "value": 10},
          {"_id": "cmd002", "key": "halk", "type": "incr", "value": 5}
        ]
      },
      "right": {
        "label": "Kaderlerine bırak",
        "commands": [
          {"_id": "cmd003", "key": "halk", "type": "decr", "value": 15}
        ]
      }
    }
  ]
}
```

---

## Card Reference

Cards are defined in the `cards` array of game.json.

### Full Card Example

```json
{
  "id": "village_fire",
  "text": "Efendim! Köyde yangın var, tamam mı?!",

  "character_id": "fatma-kabatas",
  "emotion_id": "panic",

  "left": {
    "label": "Su taşıyın!",
    "commands": [
      {"key": "hazine", "type": "decr", "value": 10},
      {"key": "halk", "type": "incr", "value": 5},
      {"key": "sound", "type": "set", "value": "water_splash"}
    ]
  },

  "right": {
    "label": "Kaderlerine bırak",
    "commands": [
      {"key": "halk", "type": "decr", "value": 15},
      {"key": "tags", "type": "push", "value": "ignored_village"},
      {"key": "sound", "type": "set", "value": "villager_cry"}
    ]
  },

  "both": {
    "commands": [
      {"key": "sound", "type": "set", "value": "fire_ambient"},
      {"key": "pool", "type": "remove", "value": "self"}
    ]
  },

  "tags": ["economy", "crisis"],
  "prereqs": [],
  "weight": {
    "base": 1.0,
    "modifiers": [
      {"metric": "hazine", "operator": "<", "value": 30, "multiplier": 2.0}
    ]
  },

  "hooks": {
    "on_draw": [
      {"key": "palette", "type": "set", "value": "fire"}
    ]
  }
}
```

### Card Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier |
| `text` | string | Yes | What the character says |
| `character_id` | string | Yes | Reference to character |
| `emotion_id` | string | Yes | Emotion state for portrait/music selection |
| `left` | Choice | No | Left swipe choice |
| `right` | Choice | No | Right swipe choice |
| `both` | Choice | No | Commands executed after any choice |
| `tags` | string[] | No | Card categorization |
| `prereqs` | string[] | No | Required game state tags to show this card |
| `weight` | Weight | No | Card selection probability |
| `hooks` | Hooks | No | Lifecycle event handlers |

### Choice Pattern Variants

**1. Standard choice** (left + right + both):
```json
"left": { "label": "Accept", "commands": [...] },
"right": { "label": "Refuse", "commands": [...] },
"both": { "commands": [...] }
```

**2. Illusion of choice** (same outcome):
```json
"left": { "label": "Evet efendim" },
"right": { "label": "Tabii ki efendim" },
"both": { "commands": [{"key": "halk", "type": "incr", "value": 5}] }
```

**3. Story card** (no real choice, just "Continue"):
```json
"both": { "commands": [{"key": "queue", "type": "push", "value": "next_story_card"}] }
```

### Execution Order

1. `hooks.on_draw` - When card appears
2. User swipes left or right
3. `left.commands` OR `right.commands` - Based on choice
4. `both.commands` - Always executed
5. `hooks.on_complete` - After all commands (future)

---

## Command System

All game state changes, UI updates, and audio are expressed as **commands** using a unified **Key-Type-Value** structure. This decouples the engine from content.

### Design Principles

- **Declarative**: Commands describe *what* to do, not *how*
- **Composable**: Multiple commands execute sequentially
- **Extensible**: New commands can be added without breaking existing content
- **UI-Agnostic**: Same commands work across web, mobile, desktop
- **Unified Structure**: All commands follow Key-Type-Value pattern

### Command Structure

```json
{
  "key": "hazine",
  "type": "decr",
  "value": 10
}
```

| Field | Description |
|-------|-------------|
| `key` | What to affect (metric, tags, queue, pool, sound, music, palette) |
| `type` | How to modify it (incr, decr, set, push, remove, flush) |
| `value` | Value to use (number, string, card_id, asset_id) |

### Key-Type-Value Matrix

Different **keys** support different **types** and expect different **value formats**:

| Key | Available Types | Value Type | Description |
|-----|----------------|------------|-------------|
| **Stats** (hazine, ordu, halk, din) | `incr`, `decr`, `set` | Number | Modify game metrics |
| `tags` | `push`, `remove`, `flush` | String (tag name) | **Boolean tags** - Triggers Tag-Delta Pool System |
| `counters` | `incr`, `decr`, `set` | String (counter name) | **Counter tags** - Numeric progression tracking |
| `queue` | `push`, `rpush`, `remove`, `flush` | String (card_id) | Urgent/planned card scheduling |
| `pool` | `push`, `remove` | String (card_id) | Manual pool overrides |
| `sound` | `set` | String (asset_id) | Play sound effect |
| `music` | `set` | String (asset_id) | Change background music |
| `palette` | `set` | String (theme_id) | Change color palette |

### Tag-Delta Pool System

**Core Innovation:** Pool composition is automatically controlled by Game Tags.

When tags are added/removed, all cards tagged with those tags automatically enter/leave the pool:

```
Previous Game Tags: [childhood, winter]
Current Game Tags:  [childhood, winter, married]
                                       ^^^^^^^^
Delta: +married → All cards with tag "married" enter pool
Delta: -winter  → All cards with tag "winter" leave pool
```

**Commands:**
```json
{"key": "tags", "type": "push", "value": "married"}
→ Adds "married" to game state
→ All cards tagged "married" automatically become drawable

{"key": "tags", "type": "remove", "value": "winter"}
→ Removes "winter" from game state
→ All cards tagged "winter" automatically become non-drawable

{"key": "tags", "type": "flush"}
→ Removes ALL game tags
→ Only cards with no required tags remain in pool
```

**Manual Pool Overrides:**

For special cases where tag-based pooling isn't enough:

```json
{"key": "pool", "type": "push", "value": "forbidden_grimoire"}
→ Add special card even if it has no matching tags

{"key": "pool", "type": "remove", "value": "self"}
→ Permanently remove this card (one-time events)
```

**Why This Design:**
- Bulk operations: One tag command can affect 50+ cards
- Replayability: Same tag, different cards appear each playthrough
- Designer-friendly: No need to manually track which cards to enable/disable

### Counter System

**Counter tags** track numeric progression (churches built, murders committed, duels won):

```json
{"key": "counters", "type": "incr", "value": "nb_churches"}
→ Increment nb_churches counter by 1

{"key": "counters", "type": "decr", "value": "nb_murders"}
→ Decrement nb_murders counter by 1

{"key": "counters", "type": "set", "value": "nb_churches", "amount": 5}
→ Set nb_churches to exactly 5
```

**Usage in Card Prerequisites:**
```json
"prereqs": ["nb_churches<8"]
→ Only show if fewer than 8 churches built

"prereqs": ["nb_murders>1", "has_queen"]
→ Murder mystery progression: 2+ murders AND queen alive
```

**Real-World Examples (from Reigns):**

**Church Building Limit:**
```json
{
  "id": "build_church",
  "text": "Bishop: Build another church?",
  "prereqs": ["nb_churches<8"],
  "right": {
    "commands": [
      {"key": "counters", "type": "incr", "value": "nb_churches"},
      {"key": "hazine", "type": "decr", "value": 20}
    ]
  }
}
```

**Murder Mystery Progression:**
```json
{
  "id": "murder_1",
  "text": "A body was found in the garden!",
  "prereqs": ["nb_murders=0"],
  "both": {
    "commands": [
      {"key": "counters", "type": "incr", "value": "nb_murders"}
    ]
  }
},
{
  "id": "murder_3_conspiracy",
  "text": "The Queen has been murdered!",
  "prereqs": ["nb_murders>1", "has_queen"],
  "both": {
    "commands": [
      {"key": "counters", "type": "incr", "value": "nb_murders"},
      {"key": "tags", "type": "push", "value": "conspiracy"}
    ]
  }
}
```

**Why Counters:**
- Enable complex progression systems
- Players "feel" the limits without seeing the code
- Replayability through hidden mechanics
- Building blocks for emergent storytelling

### Queue System

Queue is for **forced card scheduling** (story sequences, urgent events):

```json
{"key": "queue", "type": "push", "value": "assassin_investigation"}
→ Shows card NEXT (urgent - insert at beginning)

{"key": "queue", "type": "rpush", "value": "wedding_ceremony"}
→ Shows card LATER (planned - add to end)

{"key": "queue", "type": "remove", "value": "wedding_ceremony"}
→ Cancel scheduled card (e.g., due to crisis)

{"key": "queue", "type": "flush"}
→ Cancel ALL scheduled cards (revolution, chaos)
```

**Queue vs Pool:**
- **Queue**: Forced order, guaranteed appearance
- **Pool**: Random selection from available cards

### Stats Commands

Modify game metrics (hazine, ordu, halk, din):

```json
{"key": "hazine", "type": "incr", "value": 10}
→ Increase hazine by 10

{"key": "halk", "type": "decr", "value": 15}
→ Decrease halk by 15

{"key": "ordu", "type": "set", "value": 50}
→ Set ordu to exactly 50
```

### Audio/Visual Commands

```json
{"key": "sound", "type": "set", "value": "sword_clash"}
→ Play sound effect

{"key": "music", "type": "set", "value": "tense_drums"}
→ Change background music

{"key": "palette", "type": "set", "value": "fire"}
→ Change color palette
```

### Special Values

- `"self"` - References the current card (for pool/queue operations)

### Implementation Priority

| Phase | Keys + Types |
|-------|--------------|
| **MVP** | `hazine/ordu/halk/din` (incr, decr), `tags` (push, remove), `queue` (push), `pool` (remove), `sound/palette` (set) |
| **Phase 2** | `counters` (incr, decr, set), `stats` (set), `queue` (rpush, remove, flush), `pool` (push), `tags` (flush), `music` (set) |
| **Phase 3** | Conditional commands, advanced UI effects |

### Future: Conditional Commands

```json
{
  "key": "conditional",
  "type": "if",
  "condition": {"metric": "hazine", "operator": ">", "value": 50},
  "then": [
    {"key": "prestige", "type": "incr", "value": 10}
  ],
  "else": [
    {"key": "tags", "type": "push", "value": "poor"}
  ]
}
```

---

## Data Model Reference

All game entities are defined in `game.json`. Here are the key structures:

### Characters

Defined in the `characters` array:

```json
{
  "id": "fatma-kabatas",
  "name": "Fatma Kabataş",
  "role": "Saray Dadısı",
  "visual_prompt": "60-year-old woman, pearl earrings, grey-streaked hair...",
  "visual_analysis": {
    "clothing": "traditional Ottoman dress",
    "facial_features": "sharp eyes, prominent nose",
    "accessories": "pearl earrings, head covering",
    "age": "elderly",
    "distinctive_traits": "stern expression"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier |
| `name` | string | Yes | Character's display name |
| `role` | string | No | Character's position/title |
| `visual_prompt` | string | No | AI prompt for generating base portrait |
| `visual_analysis` | object | No | Vision API analysis for consistent variant generation |

### Emotions

Defined in the `emotions` array:

```json
{
  "id": "panic",
  "name": "Panik",
  "music_mood": "tense"
}
```

At runtime, the engine selects assets based on emotion:
- Portrait: Find image in `assets/characters/{character_id}/` matching emotion
- Music: Select from music tagged with `music_mood` value

### Tags

Defined in the `tags` array:

```json
{
  "id": "nb_churches",
  "name": "Churches Built",
  "type": "counter",
  "color": "#9C27B0"
}
```

**Tag Types:**
- **Boolean** (`type: "boolean"`): Presence/absence flags for storylines
- **Counter** (`type: "counter"`): Numeric values for progression tracking

### Metrics

Defined in the `metrics` array:

```json
{
  "id": "hazine",
  "name": "Hazine",
  "icon": "assets/ui/icons/hazine.png",
  "color": "#FFD700"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (used in commands) |
| `name` | string | Yes | Display name |
| `icon` | string | Yes | Asset path to icon image |
| `color` | string | No | Hex color for UI theming |

Project-specific, NOT hardcoded. Each game defines its own metrics.

### Theme

Defined in the `theme` object:

```json
{
  "palettes": {
    "default": {
      "background": "#1a1a2e",
      "surface": "#16213e",
      "text": "#eee",
      "accent": "#d4af37"
    }
  }
}
```

---

## assets/ Directory

```
assets/
├── characters/
│   └── {character-id}/
│       ├── base.png          # Default portrait
│       ├── panic.png         # Emotion variants
│       ├── happy.png
│       └── angry.png
├── music/
│   ├── tense_01.mp3
│   ├── tense_02.mp3
│   └── upbeat_01.mp3
├── sfx/
│   ├── sword_clash.mp3
│   └── fire_ambient.mp3
└── ui/
    ├── background.png
    ├── card_frame.png
    └── icons/
        ├── hazine.png
        └── ordu.png
```

### Asset Naming Convention

**Portraits:**
- Base: `base-portrait.png` (required for AI generation reference)
- Emotions: `{emotion_id}.png` (e.g., `panic.png`, `happy.png`)
- Variants: `{emotion_id}_{variant}.png` (e.g., `panic_2.png`)

**Music:** `{mood}_{number}.mp3` (e.g., `tense_01.mp3`)

**SFX:** `{name}.mp3` (e.g., `sword_clash.mp3`)

---

## What's NOT Included

The `.tahta` format is for **gameplay data only**. These are NOT exported:

| Excluded | Reason |
|----------|--------|
| `notes` fields | Internal writer documentation |
| Tasks | Editor's task tracking system |
| `created_at`, `updated_at` | Editor metadata |
| AI generation metadata | Not needed for gameplay |
| Editor-only settings | Project management stuff |

---

## Engine Loading

```python
from tahta import TahtaEngine

# Load from .tahta file (ZIP archive)
engine = TahtaEngine.from_file("osmanli-sarayi.tahta")

# Or load game.json directly (development)
engine = TahtaEngine.from_json("projects/osmanli-sarayi/game.json")

# Start game
game = engine.new_game()
card = game.draw_card()

# Process choice
game.choose("left")  # or "right"
```

---

## Changelog

### 0.3.0 (Draft) - 2025-01-17
- **Single JSON Structure**: Consolidated all data into `game.json`
  - Eliminated separate files (cards.json, characters.json, etc.)
  - Cleaner package structure: `game.json` + `assets/`
  - Simpler validation and editing workflow
- **Counter Tags System**: Numeric progression tracking (nb_churches, nb_murders)
  - `counters` commands: incr, decr, set
  - Counter prerequisites in card conditions (nb_churches<8)
  - Real-world examples from Reigns reverse engineering
- **AI Content Pipeline Integration**:
  - Added `visual_analysis` field to characters for consistent AI generation
  - Added AI config to metadata (ai_camera_angle, ai_background, ai_art_style)
  - Documented reference-based portrait generation with `base-portrait.png`
- **Tag Type System**: Separated boolean tags from counter tags
  - Tags now have `type` field: "boolean" or "counter"
  - Clear distinction in command usage and pooling behavior

### 0.2.0 (Draft)
- **Command System Redesign**: Unified Key-Type-Value structure
- **Tag-Delta Pool System**: Automatic pool management based on game tags
- **Queue System**: Urgent (push) vs planned (rpush) card scheduling
- **Flush Commands**: Reset operations (tags.flush, queue.flush)
- Updated all examples to new command format

### 0.1.0 (Draft)
- Initial specification
- Core data structures: cards, characters, emotions, metrics, tags
- Command system MVP
- Asset organization

---

## Open Questions

> Bu bölümü birlikte tartışarak dolduracağız

1. ~~**Card pooling strategy**~~: ✅ **SOLVED** - Tag-Delta Pool System + manual overrides
2. **Conditional commands**: Phase 3'te mi yoksa daha erken mi?
3. **Localization**: Multi-language support nasıl olacak?
4. **Versioning**: Format version upgrade path?
5. **Validation**: JSON Schema mı yoksa runtime validation mı?
