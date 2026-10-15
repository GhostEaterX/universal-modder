#!/usr/bin/env python3
"""Make the Egyptian God cards playable: edit the assets eds-decomp extracted from your own ROM.

    python3 apply_gods.py <eds-decomp checkout>          # apply (idempotent)
    python3 apply_gods.py <eds-decomp checkout> --check  # report only, change nothing
    python3 apply_gods.py <eds-decomp checkout> --text 3 # also the effect text, for a 3-Tribute build

Run it after `tools/dr make setup`, then `tools/dr make`. No game data lives in this script; it only
names card numbers and rewrites the extracted CSV/JSON files in place:
  - cards/stats.csv                         the Gods become 4000/4000, level 10 (type stays Divine); with
                                            --text 3, the bosses that get an effect become Effect monsters
  - cards/passwords.csv                     their TCG passwords, so the password screen hands them out
  - tables/rodata2/card_copy_limits.json    ban list: 0 copies -> GOD_COPY_LIMIT
  - tables/deck_lists.json                  Kaiba, Yami Yugi and Marik each swap one card for their God; with
                                            --text 3, also the CPU deck tuning (DECK_TUNING_3T)
  - cards/descriptions.json                 with --text 2|3 (the effects builds): the Gods' effect text in
                                            place of their flavour text, saying 2 or 3 Tributes; with 3, also
                                            the summon rules that patch_god_rules.py builds, and Senju of the
                                            Thousand Hands searching a Ritual Magic card
                                            (patch_extra_deck_rituals.py) and the bosses' effects
                                            (patch_boss_effects.py, BOSSES_3T). Each text is a fixed 480-byte
                                            record, so nothing moves
  - text/dialogue.json                      with --text 3: a new last page for the 10th-win lines of the
                                            five duelists that switch to their second deck then
                                            (patch_second_decks.py). Each record is a fixed 0x304 bytes

The C side (Divine counts as a monster type, Obelisk stops being a Ritual) is patches/eds-decomp.diff.
Stdlib only; Python 3.8+.
"""
import argparse
import csv
import io
import json
import sys
from collections import Counter
from pathlib import Path

OBELISK, SLIFER, RA = 1910, 1911, 1912
GODS = {  # card number -> (card ID, name, TCG password)
    OBELISK: (817, "Obelisk the Tormentor", "10000000"),
    SLIFER: (818, "Slifer the Sky Dragon", "10000020"),
    RA: (819, "The Winged Dragon of Ra", "10000010"),
}
GOD_ATK = GOD_DEF = 4000
GOD_LEVEL = 10
GOD_COPY_LIMIT = 1
SUMMON_TEXT = ("Requires {n} Tributes to Normal Summon (cannot be Normal Set). When Normal Summoned, cards and "
               "effects cannot be activated. ")
EFFECT_TEXT = {  # what patch_god_effects.py implements
    OBELISK: "Neither player can target this card with card effects. You can Tribute 2 other monsters to "
             "destroy all monsters your opponent controls. This card cannot attack the turn this effect is "
             "activated.",
    SLIFER: "This card's ATK and DEF are 1000 x the number of cards in your hand. If your opponent Normal or "
            "Special Summons a monster in Attack Position: it loses 2000 ATK, then if its ATK has been "
            "reduced to 0 as a result, destroy it.",
    RA: "When this card is Normal Summoned, you can pay Life Points so that you only have 100 left: its ATK "
        "and DEF become the amount paid. You can pay 1000 Life Points to destroy 1 monster on the field.",
}
# The three-Tribute effects build also has the TCG summon rules (patch_god_rules.py).
RULES_TEXT_3T = {
    OBELISK: (" If this card is Special Summoned, it is sent to the Graveyard during the End Phase.", ""),
    SLIFER: (" If this card is Special Summoned, it is sent to the Graveyard during the End Phase.", ""),
    RA: ("", "Cannot be Special Summoned. "),      # (after the effect text, before it)
}
TEXT_RECORD = 0x1E0
# The three-Tribute effects build also switches Yugi, Tea, Joey, Tristan and Bakura to their second deck after
# the player's 10th win against them (patch_second_decks.py). Their 10th-win line (gOpponentResultTexts[duelist]
# .win10th, shown when the record still says 9 wins) gets a new last page that says so.
# dialogue event -> (speaker = duelist ID, the new page)
SECOND_DECK_PAGES = {
    1017: (1, "I better find some new cards and train more. Next time, I'll be ready for you!"),
    2017: (2, "Just kidding! I better find some new cards and train more. Next time, I'm going to win!"),
    3017: (3, "Nah, forget that! I better find some new cards and train more. Next time, ya won't know what hit ya!"),
    4017: (4, "Then again... I better find some new cards and train more. Next time, I'm not going easy on you!"),
    5016: (5, "I better find some new cards and train more. Next time, I'll give you a real challenge."),
}
PAGE_BREAK = "$c$p"                 # wait for A, then a new page (the game's own code for it)

# The three-Tribute effects build also tunes the CPU decks: every card the CPU can never play (no rule in its
# code plays, sets off or chains it: Snatch Steal, Spellbinding Circle, Kunai with Chain, Solemn Judgment, Horn
# of Heaven, Sebek's Blessing, Metalmorph, Time Machine, 7 Completed, and Megamorph outside Kaiba's Cyber-Stein
# combo) and a few generic cards give way to cards that fit the duelist and that the CPU does play. Swaps are
# one for one, so the deck region still fits. (deck table, duelist ID) -> [(card number, copies before,
# copies after)]; the names are for reading only. A deck is changed only when it holds exactly the "before"
# counts, and left alone when it already holds the "after" ones.
O, A = "opponent_decks", "alternate_decks"
DECK_TUNING_3T = {
    (A, 1): [   # Yugi Muto, second deck
        (1068, 1, 0),  # Snatch Steal
        (1095, 0, 1),  # Call Of The Haunted
    ],
    (A, 2): [   # Tea Gardner, second deck
        (348, 1, 0),   # Spellbinding Circle
        (1092, 0, 1),  # Gift of The Mystical Elf
    ],
    (O, 3): [   # Joey Wheeler
        (336, 1, 0),   # Raigeki
        (15, 1, 2),    # Time Wizard
    ],
    (A, 3): [   # Joey Wheeler, second deck
        (650, 1, 0),   # Kunai with Chain
        (15, 0, 1),    # Time Wizard
        (657, 1, 0),   # Metalmorph
        (1204, 0, 1),  # Skull Dice
    ],
    (A, 4): [   # Tristan Taylor, second deck
        (1068, 1, 0),  # Snatch Steal
        (640, 0, 1),   # Invader of the Throne
        (671, 1, 0),   # Harpie's Feather Duster
        (223, 0, 1),   # Trap Master
    ],
    (O, 5): [   # Bakura Ryou
        (348, 1, 0),   # Spellbinding Circle
        (1095, 0, 1),  # Call Of The Haunted
        (550, 3, 2),   # Dark Elf
        (1123, 0, 1),  # Mystic Tomato
    ],
    (A, 5): [   # Bakura Ryou, second deck
        (348, 1, 0),   # Spellbinding Circle
        (1095, 0, 1),  # Call Of The Haunted
        (550, 3, 2),   # Dark Elf
        (1123, 0, 1),  # Mystic Tomato
    ],
    (O, 6): [   # Rex Raptor
        (1068, 1, 0),  # Snatch Steal
        (1001, 0, 2),  # Fissure
        (336, 1, 0),   # Raigeki
        (573, 2, 0),   # Witch of the Black Forest
        (1108, 1, 3),  # Giant Rat
    ],
    (O, 7): [   # Espa Roba
        (962, 2, 0),   # 7 Completed
        (742, 0, 2),   # Barrel Dragon
        (950, 1, 0),   # Time Machine
        (414, 2, 3),   # Mechanicalchaser
    ],
    (O, 8): [   # Weevil Underwood
        (1068, 1, 0),  # Snatch Steal
        (1120, 0, 3),  # Flying Kamakiri #1
        (531, 2, 0),   # Gemini Elf
    ],
    (O, 9): [   # Mako Tsunami
        (650, 2, 0),   # Kunai with Chain
        (1119, 0, 3),  # Mother Grizzly
        (1068, 1, 0),  # Snatch Steal
        (550, 1, 0),   # Dark Elf
        (446, 0, 1),   # Giant Red Seasnake
    ],
    (O, 10): [   # Mai Valentine
        (1068, 1, 0),  # Snatch Steal
        (62, 0, 1),    # Harpie Lady Sisters
        (573, 2, 0),   # Witch of the Black Forest
        (1120, 0, 2),  # Flying Kamakiri #1
    ],
    (O, 11): [   # Rare Hunter
        (1031, 1, 0),  # Horn of Heaven
        (960, 1, 2),   # Negate Attack
    ],
    (O, 12): [   # Arkana
        (1068, 1, 0),  # Snatch Steal
        (759, 1, 2),   # Dark Magician Girl
        (73, 3, 0),    # Giant Soldier of Stone
        (1, 0, 3),     # Mystical Elf
    ],
    (O, 13): [   # Strings
        (1068, 1, 0),  # Snatch Steal
        (1095, 0, 1),  # Call Of The Haunted
    ],
    (O, 14): [   # Umbra & Lumis
        (348, 1, 0),   # Spellbinding Circle
        (101, 0, 2),   # Mask of Darkness
        (1031, 1, 0),  # Horn of Heaven
        (1068, 1, 0),  # Snatch Steal
        (83, 0, 1),    # Reaper of the Cards
        (531, 2, 0),   # Gemini Elf
        (378, 0, 2),   # La Jinn the Mystical Genie of the Lamp
    ],
    (O, 15): [   # Marik Ishtar
        (1068, 1, 0),  # Snatch Steal
        (640, 0, 1),   # Invader of the Throne
        (1179, 1, 0),  # Sebek's Blessing
        (1095, 0, 1),  # Call Of The Haunted
    ],
    (O, 16): [   # Kaiba Seto
        (1028, 1, 0),  # Solemn Judgment
        (960, 0, 1),   # Negate Attack
        (1068, 1, 0),  # Snatch Steal
        (1160, 0, 1),  # Premature Burial
        (1179, 2, 0),  # Sebek's Blessing
        (740, 0, 1),   # Lord of D.
        (1003, 0, 1),  # Polymerization, so the two Blue-Eyes Ultimate Dragons can come out without Cyber-Stein
    ],
    (O, 17): [   # Ishizu Ishtar
        (657, 2, 0),   # Metalmorph
        (1140, 0, 2),  # Numinous Healer
        (1028, 1, 0),  # Solemn Judgment
        (960, 0, 2),   # Negate Attack
        (1031, 1, 0),  # Horn of Heaven
    ],
    (O, 18): [   # Shadi
        (1028, 1, 0),  # Solemn Judgment
        (83, 2, 3),    # Reaper of the Cards
    ],
    (O, 19): [   # Yami Bakura
        (650, 1, 0),   # Kunai with Chain
        (83, 0, 1),    # Reaper of the Cards
        (1061, 2, 1),  # Heavy Storm
        (1123, 0, 1),  # Mystic Tomato
        (837, 3, 0),   # Vorse Raider
        (378, 0, 3),   # La Jinn the Mystical Genie of the Lamp
    ],
    (O, 20): [   # Yami Yugi
        (1068, 1, 0),  # Snatch Steal
        (1095, 0, 1),  # Call Of The Haunted
    ],
    (O, 21): [   # Duel Computer
        (1068, 1, 0),  # Snatch Steal
        (101, 2, 3),   # Mask of Darkness
        (113, 3, 1),   # White Magical Hat
        (742, 0, 2),   # Barrel Dragon, a boss with an effect for a deck that had none
    ],
    (O, 22): [   # Simon
        (1068, 1, 0),  # Snatch Steal
        (960, 0, 1),   # Negate Attack
    ],
    (O, 23): [   # Maximillion Pegasus
        (950, 1, 0),   # Time Machine
        (727, 0, 3),   # Toon Mermaid
        (1028, 1, 0),  # Solemn Judgment
        (656, 1, 0),   # Megamorph
    ],
    (O, 24): [   # Trusdale
        (348, 1, 0),   # Spellbinding Circle
        (960, 0, 1),   # Negate Attack
        (1068, 1, 0),  # Snatch Steal
        (1095, 0, 1),  # Call Of The Haunted
    ],
}
DIALOGUE_TEXT = 0x300               # text bytes per dialogue record, NUL included
# The three-Tribute effects build also moves the Ritual monsters to the Fusion Deck (patch_extra_deck_rituals.py),
# so Senju of the Thousand Hands searches a Ritual Magic card instead of a Ritual monster: its new text.
SENJU = (1109, "Senju of the Thousand Hands")     # card number, name
SENJU_TEXT_3T = ("When this card is Normal Summoned or Flip Summoned, you can add 1 Ritual Magic card from your "
                 "Deck to your hand. Then shuffle your Deck.")
# The three-Tribute effects build also gives the CPU duelists' Normal-monster bosses an effect
# (patch_boss_effects.py). card ID -> (name, Effect monster, the new text). They become Effect monsters: the kind
# gives a monster effect spell speed 1 (and the card its orange frame).
BOSSES_3T = {
    675: ("Summoned Skull", True,
          "If this card attacks a Defense Position monster, inflict piercing battle damage to your opponent: the "
          "amount this card's ATK exceeds that monster's DEF."),
    471: ("Millennium Golem", True,
          "This card cannot be destroyed by battle. Its controller still takes any battle damage."),
    150: ("Dark Magician", True,
          "Once per turn: you can target 1 Spell or Trap card your opponent controls; destroy that target."),
    151: ("Dark Magician", True,
          "Once per turn: you can target 1 Spell or Trap card your opponent controls; destroy that target."),
    579: ("Red-Eyes B. Dragon", True,
          "Once per turn: you can target 1 monster your opponent controls; toss a coin. If the result is Heads, "
          "destroy that target. While this card is equipped with Metalmorph, its activation Tributes it instead, "
          "to Special Summon 1 Red-Eyes Black Metal Dragon from your Deck."),
    580: ("Red-Eyes Black Metal Dragon", False,
          "Special Summoned from your Deck by Tributing a Red-Eyes B. Dragon equipped with Metalmorph. If this "
          "card attacks a monster, it gains ATK equal to 1/4 of that monster's ATK, during damage calculation "
          "only."),
}
KIND_NORMAL, KIND_EFFECT = "0", "1"
# opponent deck index (= duelist ID) -> (card number given up, God given). Deck sizes stay the same, so
# the 0x920-byte deck region still fits.
DECK_SWAPS = {
    16: (30, OBELISK),   # Kaiba Seto: one of three Koumori Dragon
    20: (73, SLIFER),    # Yami Yugi: Giant Soldier of Stone
    15: (119, RA),       # Marik Ishtar: one of three Dream Clown
}


def _depth(value):
    if isinstance(value, dict):
        return 1 + max((_depth(v) for v in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_depth(v) for v in value), default=0)
    return 0


def dump_json(value, indent=0, width=112):
    """The extractor's JSON style (eds-decomp tools/assetfmt/tables_game.py), so a rewrite only shows the
    lines that changed: one space per level, short shallow containers on one line, long scalar lists
    wrapped at `width`."""
    flat = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    if not isinstance(value, (list, dict)) or len(flat) + indent <= width and _depth(value) <= 2:
        return flat
    pad = " " * (indent + 1)
    if isinstance(value, dict):
        body = [f"{pad}{json.dumps(k)}: {dump_json(v, indent + 1, width)}" for k, v in value.items()]
        return "{\n" + ",\n".join(body) + "\n" + " " * indent + "}"
    if all(not isinstance(x, (list, dict)) for x in value):
        lines, cur = [], []
        for x in value:
            s = json.dumps(x, ensure_ascii=False)
            if cur and len(pad) + sum(len(c) + 2 for c in cur) + len(s) > width:
                lines.append(", ".join(cur))
                cur = []
            cur.append(s)
        lines.append(", ".join(cur))
        return "[\n" + ",\n".join(pad + ln for ln in lines) + "\n" + " " * indent + "]"
    return "[\n" + ",\n".join(pad + dump_json(x, indent + 1, width) for x in value) + "\n" + " " * indent + "]"


def load_json(path):
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if dump_json(data) + "\n" != text:
        sys.exit(f"{path}: unexpected formatting, refusing to rewrite it (re-run tools/dr make setup?)")
    return data


def read_csv(path):
    text = path.read_text()
    rows = list(csv.DictReader(io.StringIO(text)))
    if write_csv_text(rows, list(rows[0])) != text:
        sys.exit(f"{path}: unexpected formatting, refusing to rewrite it")
    return rows


def write_csv_text(rows, fields):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path, help="eds-decomp checkout with assets/ extracted")
    ap.add_argument("--check", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--text", type=int, choices=(2, 3), help="write the effect text, with this many Tributes")
    args = ap.parse_args()
    assets = args.decomp / "assets"
    if not (assets / "cards" / "stats.csv").exists():
        sys.exit(f"{assets}: no extracted assets; run tools/dr make setup first")
    changes = []

    # Stats: 4000/4000, level 10. ATK and DEF are stored divided by 10.
    path = assets / "cards" / "stats.csv"
    rows = read_csv(path)
    by_id = {int(r["id"]): r for r in rows}
    for number, (card_id, name, _) in GODS.items():
        r = by_id[card_id]
        if r["name"] != name:
            sys.exit(f"stats.csv: ID {card_id} is {r['name']!r}, expected {name!r} (not the USA ROM?)")
        want = {"atk": str(GOD_ATK // 10), "def": str(GOD_DEF // 10), "level": str(GOD_LEVEL)}
        diff = {k: v for k, v in want.items() if r[k] != v}
        if diff:
            changes.append(f"stats {name}: " + ", ".join(f"{k} {r[k]} -> {v}" for k, v in diff.items()))
            r.update(diff)
    # The bosses with an effect (three-Tribute effects build only): Effect monsters.
    if args.text == 3:
        for card_id, (name, effect, _) in BOSSES_3T.items():
            r = by_id[card_id]
            if r["name"] != name:
                sys.exit(f"stats.csv: ID {card_id} is {r['name']!r}, expected {name!r} (not the USA ROM?)")
            if effect and r["kind"] != KIND_EFFECT:
                if r["kind"] != KIND_NORMAL:
                    sys.exit(f"stats.csv: {name} (ID {card_id}) has kind {r['kind']}, expected a Normal monster")
                changes.append(f"stats {name} (ID {card_id}): Normal -> Effect monster")
                r["kind"] = KIND_EFFECT
    if not args.check:
        path.write_text(write_csv_text(rows, list(rows[0])))

    # Passwords.
    path = assets / "cards" / "passwords.csv"
    rows = read_csv(path)
    by_id = {int(r["id"]): r for r in rows}
    taken = {r["password"]: r["name"] for r in rows if r["password"]}
    for number, (card_id, name, password) in GODS.items():
        r = by_id[card_id]
        if r["password"] != password:
            if password in taken:
                sys.exit(f"password {password} already belongs to {taken[password]}")
            changes.append(f"password {name}: {r['password'] or 'none'} -> {password}")
            r["password"] = password
    if not args.check:
        path.write_text(write_csv_text(rows, list(rows[0])))

    # Ban list.
    path = assets / "tables" / "rodata2" / "card_copy_limits.json"
    data = load_json(path)
    for e in data["entries"]:
        if e["card"] in GODS and e["limit"] != GOD_COPY_LIMIT:
            changes.append(f"copy limit {e['_card']}: {e['limit']} -> {GOD_COPY_LIMIT}")
            e["limit"] = GOD_COPY_LIMIT
    if not args.check:
        path.write_text(dump_json(data) + "\n", encoding="utf-8")

    # NPC decks: drop one copy of the given-up card, append the God (the highest number, so the
    # list stays ascending like the original data).
    path = assets / "tables" / "deck_lists.json"
    data = load_json(path)
    for deck_index, (old, god) in DECK_SWAPS.items():
        deck = data["opponent_decks"][deck_index]
        cards = deck["cards"]
        if any(n == god for n, _ in cards):
            continue
        for i, (n, name) in enumerate(cards):
            if n == old:
                del cards[i]
                cards.append([god, GODS[god][1]])
                changes.append(f"deck {deck['_duelist']}: {name} -> {GODS[god][1]}")
                break
        else:
            sys.exit(f"deck {deck['_duelist']}: card {old} not found")
    # CPU deck tuning (three-Tribute effects build only).
    if args.text == 3:
        names = json.loads((assets / "cards" / "names.json").read_text(encoding="utf-8"))
        number_to_id = json.loads((assets / "cards" / "number_to_id.json").read_text(encoding="utf-8"))
        for (table, index), rows in DECK_TUNING_3T.items():
            deck = data[table][index]
            have = Counter(n for n, _ in deck["cards"])
            if all(have[n] == after for n, _, after in rows):
                continue
            if any(have[n] != before for n, before, _ in rows):
                sys.exit(f"deck {deck['_duelist']}: not the cards the tuning expects (not the USA ROM?)")
            cards = deck["cards"]
            for n, before, after in rows:
                for _ in range(before - after):
                    cards.remove(next(c for c in cards if c[0] == n))
                cards.extend([n, names[number_to_id[n]]] for _ in range(after - before))
            cards.sort(key=lambda c: c[0])      # ascending, like the original lists
            changes.append(f"deck {deck['_duelist']}{' (second deck)' if table == A else ''}: "
                           f"{sum(max(0, b - a) for _, b, a in rows)} card(s) swapped")
    if not args.check:
        path.write_text(dump_json(data) + "\n", encoding="utf-8")

    # Card text (effects builds only).
    if args.text:
        path = assets / "cards" / "descriptions.json"
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if json.dumps(data, ensure_ascii=False, indent=1) + "\n" != raw:
            sys.exit(f"{path}: unexpected formatting, refusing to rewrite it")
        for number, (card_id, name, _) in GODS.items():
            after, before = RULES_TEXT_3T[number] if args.text == 3 else ("", "")
            text = SUMMON_TEXT.format(n=args.text) + before + EFFECT_TEXT[number] + after
            if len(text.encode("ascii")) >= TEXT_RECORD:
                sys.exit(f"{name}: the text is longer than its {TEXT_RECORD}-byte record")
            if data[card_id] != text:
                changes.append(f"text {name}: {len(text)} characters")
                data[card_id] = text
        if args.text == 3:
            number, name = SENJU
            card_id = json.loads((assets / "cards" / "number_to_id.json").read_text(encoding="utf-8"))[number]
            names = json.loads((assets / "cards" / "names.json").read_text(encoding="utf-8"))
            if names[card_id] != name:
                sys.exit(f"card number {number} is {names[card_id]!r}, expected {name!r} (not the USA ROM?)")
            if data[card_id] != SENJU_TEXT_3T:
                changes.append(f"text {name}: searches a Ritual Magic card")
                data[card_id] = SENJU_TEXT_3T
            for card_id, (name, _, text) in BOSSES_3T.items():
                if names[card_id] != name:
                    sys.exit(f"card ID {card_id} is {names[card_id]!r}, expected {name!r} (not the USA ROM?)")
                if len(text.encode("ascii")) >= TEXT_RECORD:
                    sys.exit(f"{name}: the text is longer than its {TEXT_RECORD}-byte record")
                if data[card_id] != text:
                    changes.append(f"text {name} (ID {card_id}): its effect, {len(text)} characters")
                    data[card_id] = text
        if not args.check:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # The 10th-win lines (three-Tribute effects build only).
    if args.text == 3:
        path = assets / "text" / "dialogue.json"
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if json.dumps(data, ensure_ascii=False, indent=1) + "\n" != raw:
            sys.exit(f"{path}: unexpected formatting, refusing to rewrite it")
        by_event = {r["event"]: r for r in data}
        for event, (speaker, page) in SECOND_DECK_PAGES.items():
            r = by_event.get(event)
            if r is None or r["speaker"] != speaker:
                sys.exit(f"dialogue {event}: not duelist {speaker}'s line (not the USA ROM?)")
            if r["text"].endswith(PAGE_BREAK + page):
                continue
            r["text"] += PAGE_BREAK + page
            if len(r["text"].encode("ascii")) >= DIALOGUE_TEXT:
                sys.exit(f"dialogue {event}: the text is longer than its {DIALOGUE_TEXT}-byte record")
            changes.append(f"dialogue {event} (duelist {speaker}): a new last page")
        if not args.check:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    verb = "would change" if args.check else "changed"
    print(f"{verb} {len(changes)} thing(s)" + (":" if changes else " (already applied)"))
    for c in changes:
        print("  " + c)


if __name__ == "__main__":
    main()
