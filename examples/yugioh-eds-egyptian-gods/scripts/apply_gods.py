#!/usr/bin/env python3
"""Make the Egyptian God cards playable: edit the assets eds-decomp extracted from your own ROM.

    python3 apply_gods.py <eds-decomp checkout>          # apply (idempotent)
    python3 apply_gods.py <eds-decomp checkout> --check  # report only, change nothing
    python3 apply_gods.py <eds-decomp checkout> --text 3 # also the effect text, for a 3-Tribute build

Run it after `tools/dr make setup`, then `tools/dr make`. No game data lives in this script; it only
names card numbers and rewrites the extracted CSV/JSON files in place:
  - cards/stats.csv                         the Gods become 4000/4000, level 10 (type stays Divine)
  - cards/passwords.csv                     their TCG passwords, so the password screen hands them out
  - tables/rodata2/card_copy_limits.json    ban list: 0 copies -> GOD_COPY_LIMIT
  - tables/deck_lists.json                  Kaiba, Yami Yugi and Marik each swap one card for their God
  - cards/descriptions.json                 with --text 2|3 (the effects builds): the Gods' effect text in
                                            place of their flavour text, saying 2 or 3 Tributes. Each text
                                            is a fixed 480-byte record, so nothing moves

The C side (Divine counts as a monster type, Obelisk stops being a Ritual) is patches/eds-decomp.diff.
Stdlib only; Python 3.8+.
"""
import argparse
import csv
import io
import json
import sys
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
TEXT_RECORD = 0x1E0
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
            text = SUMMON_TEXT.format(n=args.text) + EFFECT_TEXT[number]
            if len(text.encode("ascii")) >= TEXT_RECORD:
                sys.exit(f"{name}: the text is longer than its {TEXT_RECORD}-byte record")
            if data[card_id] != text:
                changes.append(f"text {name}: {len(text)} characters")
                data[card_id] = text
        if not args.check:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    verb = "would change" if args.check else "changed"
    print(f"{verb} {len(changes)} thing(s)" + (":" if changes else " (already applied)"))
    for c in changes:
        print("  " + c)


if __name__ == "__main__":
    main()
