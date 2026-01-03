#!/usr/bin/env python3
"""
Tek bir kartı Gemini ile render et.

Kullanım:
    python tools/render_card.py tower
    python tools/render_card.py tower --show
    python tools/render_card.py tower --output /tmp/test.png
"""

import argparse
import json
import urllib.request
import base64
import sys
from pathlib import Path

API_KEY = "AIzaSyClzCZydrY4hnhaVPdK4IvSHMOkjEB-Zzg"
MODEL = "gemini-2.0-flash-exp-image-generation"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

# Template dosyası (ornate border with two empty boxes)
TEMPLATE_PATH = "/tmp/card_template.jpg"

# Proje kök dizini
PROJECT_ROOT = Path(__file__).parent.parent
GAME_JSON = PROJECT_ROOT / "experiments/preact-runtime/public/game.json"
OUTPUT_DIR = PROJECT_ROOT / "experiments/preact-runtime/public/cards"

# Karakter açıklamaları (görsel için)
CHARACTER_VISUALS = {
    "general": "a stern military general in medieval armor with medals",
    "priest": "a catholic priest in brown robes holding a cross",
    "merchant": "a wealthy merchant with fine clothes and gold coins",
    "doctor": "a plague doctor with bird-like mask and black robes",
    "diplomat": "a refined diplomat in elegant court attire with scrolls",
    "nobleman": "an arrogant nobleman with fancy hat and jeweled rings",
    "queen": "a beautiful queen with golden crown and royal robes",
    "jester": "a colorful court jester with bells and motley costume",
    "monk": "a humble monk in simple brown robes, bald head",
    "spy": "a shadowy spy in dark hooded cloak, half-hidden face",
    "executioner": "a hooded executioner in black with an axe",
    "lady": "a noble lady in elegant dress with embroidery",
    "farmer": "a simple peasant farmer with straw hat and pitchfork",
    "witch": "an old crone witch with wild gray hair and potions",
    "fortune_teller": "a mystical fortune teller with crystal ball and scarves",
    "nun": "a devout nun in black and white habit with rosary",
    "courtesan": "an alluring courtesan with elegant dress and roses",
    "dog": "a loyal royal hunting dog with decorative collar",
    "skeleton": "a grinning skeleton in tattered robes with hourglass",
    "ghost": "a translucent ghost of a nobleman, ethereal and pale",
    "prophet": "an ancient bearded prophet with wild eyes and tablets",
    "dragon": "a fearsome dragon head with scales and glowing eyes",
    "bird": "a majestic raven with intelligent eyes and glossy feathers",
    "homunculus": "a tiny alchemical creature in a glass jar",
    "foreign_princess": "an exotic princess with ornate eastern headdress",
    "barbare": "a fierce viking warrior with horned helmet and axe",
    "explorator": "a weathered explorer with compass and maps",
    "prince": "a young handsome prince with golden crown",
    "rival": "a scheming rival nobleman with dark plotting expression",
    "minstrel": "a traveling minstrel with lute and colorful clothes",
    "painter": "a renaissance painter with palette and brushes",
    "parker": "a medieval park keeper with simple clothes and keys",
    "werewolf": "a terrifying werewolf with fur and glowing eyes",
    "black_bird": "an ominous black raven, harbinger of doom",
    "soldier": "a common foot soldier in chainmail with spear",
    "anyone": "a mysterious hooded figure with hidden face",
}


def load_game_data():
    """game.json'u yükle"""
    with open(GAME_JSON, 'r') as f:
        return json.load(f)


def get_card(game_data, card_id):
    """Belirli bir kartı getir"""
    cards = game_data.get('cards', {})
    if card_id not in cards:
        available = list(cards.keys())[:10]
        raise ValueError(f"Kart bulunamadı: {card_id}\nÖrnek kartlar: {available}")
    return cards[card_id]


def generate_card_image(card_id, card, game_data):
    """Gemini ile kart görseli üret (img2img + mask)"""

    # Kart bilgilerini al
    text = card.get('text', '')
    bearer = card.get('bearer', {})
    character_id = bearer.get('character', 'anyone') if isinstance(bearer, dict) else 'anyone'

    # Karakter görsel açıklaması
    character_visual = CHARACTER_VISUALS.get(character_id, "a mysterious medieval figure")

    # Karakter adını al
    characters = game_data.get('characters', {})
    character_name = characters.get(character_id, {}).get('name', character_id.title())

    # Template'i yükle
    with open(TEMPLATE_PATH, 'rb') as f:
        template_data = base64.b64encode(f.read()).decode('utf-8')

    prompt = json.dumps({
        "task": "Fill the two empty boxes in the provided medieval card template",
        "template_instructions": {
            "top_box": f"Draw {character_visual} with dark cross-hatched background (diagonal lines, not solid black)",
            "bottom_box": f"Write in medieval script: '{character_name}' on first line, then '{text}'",
            "border": "Keep exactly as is - do not modify"
        },
        "style_identity": "Classic Baroque Engraving & Master Etching",
        "canvas_and_medium": {
            "substrate": "Heavyweight antique parchment, cold-press texture",
            "base_color": "Aged ivory / Warm bone (#F5F2E7)",
            "surface_effects": "Subtle foxing, paper fiber grain, matte finish"
        },
        "ink_and_pen_physics": {
            "instrument": "Fine-point steel nib and quill",
            "ink_type": "Iron gall ink (deep carbon black with slight sepia oxidation on edges)",
            "line_weight": {
                "range": "0.1mm to 0.4mm",
                "dynamic": "Pressure-sensitive tapering (thick-to-thin strokes)",
                "edge_quality": "Micro-feathering (ink absorption into paper fibers)"
            },
            "density_profile": {
                "black_point": "Deepest shadows at 95-100% opacity",
                "midtone_hatching": "70-85% opacity due to fine line spacing",
                "buildup": "Concentrated ink deposits at cross-hatch intersections"
            },
            "shading_logic": {
                "primary_method": "Cross-hatching and contour-hatching",
                "secondary_method": "Stippling (fine dots) for organic skin transitions",
                "directional_flow": "Lines follow the 3D topography of the object"
            }
        },
        "character_rendering": {
            "pose": "Three-quarter profile, classical posture",
            "lighting": "High-contrast chiaroscuro (Top-left key light)",
            "textile_detail": "Intricate etching of fabric weaves, metallic sheen on armor"
        },
        "execution_rules": {
            "anti_aliasing": "None (Sharp, pixel-perfect ink edges)",
            "grain_integration": "Simulated plate-tone",
            "imperfections": ["Intermittent broken lines", "Manual jitter", "Asymmetric hand-drawn feel"]
        },
        "prohibited": [
            "Digital gradients",
            "Soft airbrushing",
            "Vector smoothness",
            "Solid black fills without hatching",
            "Modern colors",
            "Sans-serif fonts"
        ]
    }, indent=2)

    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": template_data
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": 0.6,  # Daha tutarlı sonuçlar için düşük
            "topP": 0.85,
            "topK": 32
        }
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode('utf-8'))

        # Görseli bul
        for candidate in data.get('candidates', []):
            for part in candidate.get('content', {}).get('parts', []):
                if 'inlineData' in part:
                    return base64.b64decode(part['inlineData']['data'])

        return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:500]
        print(f"API Hatası: {e.code}\n{error_body}", file=sys.stderr)
        return None


def generate_character_avatar(character_id):
    """Sadece karakter avatarı üret (kart olmadan)"""

    character_visual = CHARACTER_VISUALS.get(character_id, "a mysterious medieval figure")
    character_name = character_id.replace('_', ' ').title()

    # Template'i yükle
    with open(TEMPLATE_PATH, 'rb') as f:
        template_data = base64.b64encode(f.read()).decode('utf-8')

    prompt = json.dumps({
        "task": "Fill the two empty boxes in the provided medieval card template",
        "template_instructions": {
            "top_box": f"Draw {character_visual} with dark cross-hatched background (diagonal lines, not solid black)",
            "bottom_box": f"Write in medieval script: '{character_name}'",
            "border": "Keep exactly as is - do not modify"
        },
        "style_identity": "Classic Baroque Engraving & Master Etching",
        "canvas_and_medium": {
            "substrate": "Heavyweight antique parchment, cold-press texture",
            "base_color": "Aged ivory / Warm bone (#F5F2E7)",
            "surface_effects": "Subtle foxing, paper fiber grain, matte finish"
        },
        "ink_and_pen_physics": {
            "instrument": "Fine-point steel nib and quill",
            "ink_type": "Iron gall ink (deep carbon black with slight sepia oxidation on edges)",
            "line_weight": {
                "range": "0.1mm to 0.4mm",
                "dynamic": "Pressure-sensitive tapering (thick-to-thin strokes)",
                "edge_quality": "Micro-feathering (ink absorption into paper fibers)"
            },
            "density_profile": {
                "black_point": "Deepest shadows at 95-100% opacity",
                "midtone_hatching": "70-85% opacity due to fine line spacing",
                "buildup": "Concentrated ink deposits at cross-hatch intersections"
            },
            "shading_logic": {
                "primary_method": "Cross-hatching and contour-hatching",
                "secondary_method": "Stippling (fine dots) for organic skin transitions",
                "directional_flow": "Lines follow the 3D topography of the object"
            }
        },
        "character_rendering": {
            "pose": "Three-quarter profile, classical posture",
            "lighting": "High-contrast chiaroscuro (Top-left key light)",
            "textile_detail": "Intricate etching of fabric weaves, metallic sheen on armor"
        },
        "execution_rules": {
            "anti_aliasing": "None (Sharp, pixel-perfect ink edges)",
            "grain_integration": "Simulated plate-tone",
            "imperfections": ["Intermittent broken lines", "Manual jitter", "Asymmetric hand-drawn feel"]
        },
        "prohibited": [
            "Digital gradients",
            "Soft airbrushing",
            "Vector smoothness",
            "Solid black fills without hatching",
            "Modern colors",
            "Sans-serif fonts"
        ]
    }, indent=2)

    payload = {
        "contents": [{
            "parts": [
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": template_data
                    }
                },
                {"text": prompt}
            ]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE", "TEXT"],
            "temperature": 0.6,
            "topP": 0.85,
            "topK": 32
        }
    }

    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            data = json.loads(response.read().decode('utf-8'))

        for candidate in data.get('candidates', []):
            for part in candidate.get('content', {}).get('parts', []):
                if 'inlineData' in part:
                    return base64.b64decode(part['inlineData']['data'])

        return None

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:500]
        print(f"API Hatası: {e.code}\n{error_body}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description='Tek bir kartı Gemini ile render et')
    parser.add_argument('card_id', help='Render edilecek kart ID\'si veya karakter ID\'si (--character ile)')
    parser.add_argument('--output', '-o', help='Çıktı dosya yolu (varsayılan: cards/<card_id>.png)')
    parser.add_argument('--show', '-s', action='store_true', help='Görseli göster (macOS)')
    parser.add_argument('--info', '-i', action='store_true', help='Sadece kart bilgisini göster')
    parser.add_argument('--character', '-c', action='store_true', help='Karakter avatarı üret (kart yerine)')

    args = parser.parse_args()

    # Karakter modu
    if args.character:
        character_id = args.card_id
        print(f"\n👤 Karakter: {character_id}")
        print(f"📝 Açıklama: {CHARACTER_VISUALS.get(character_id, 'bilinmiyor')}")

        output_path = Path(args.output) if args.output else OUTPUT_DIR / f"{character_id}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n🎨 Avatar üretiliyor...")
        image_data = generate_character_avatar(character_id)

        if image_data:
            with open(output_path, 'wb') as f:
                f.write(image_data)

            size_kb = len(image_data) / 1024
            print(f"✅ Kaydedildi: {output_path} ({size_kb:.1f} KB)")

            if args.show:
                import subprocess
                subprocess.run(['open', str(output_path)])
        else:
            print("❌ Avatar üretilemedi!")
            sys.exit(1)
        return

    # Oyun verisini yükle
    print(f"📂 Oyun verisi yükleniyor...")
    game_data = load_game_data()

    # Kartı al
    card = get_card(game_data, args.card_id)

    # Kart bilgisi
    bearer = card.get('bearer', {})
    character_id = bearer.get('character', 'anyone') if isinstance(bearer, dict) else 'anyone'
    print(f"\n🎴 Kart: {args.card_id}")
    print(f"👤 Karakter: {character_id}")
    print(f"💬 Metin: {card.get('text', '')[:80]}...")

    if args.info:
        print(f"\n📋 Tam veri:\n{json.dumps(card, indent=2)}")
        return

    # Çıktı yolu
    output_path = Path(args.output) if args.output else OUTPUT_DIR / f"{args.card_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Görsel üret
    print(f"\n🎨 Görsel üretiliyor...")
    image_data = generate_card_image(args.card_id, card, game_data)

    if image_data:
        with open(output_path, 'wb') as f:
            f.write(image_data)

        size_kb = len(image_data) / 1024
        print(f"✅ Kaydedildi: {output_path} ({size_kb:.1f} KB)")

        if args.show:
            import subprocess
            subprocess.run(['open', str(output_path)])
    else:
        print("❌ Görsel üretilemedi!")
        sys.exit(1)


if __name__ == "__main__":
    main()
