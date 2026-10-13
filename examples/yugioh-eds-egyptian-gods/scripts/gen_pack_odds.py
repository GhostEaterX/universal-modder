#!/usr/bin/env python3
"""The pack viewer's odds table: the chance of each card being in a pack from the pick-a-pack screen, computed
from your own booster_packs.json (eds-decomp's `make setup` extracts it). patch_pack_viewer.py writes the table
into the mod tree at build time. It holds the game's card lists, so it is never committed.

    gen_pack_odds.py <booster_packs.json> <out.h>          # the table src/pack_viewer.c includes
    gen_pack_odds.py <booster_packs.json> --show <pack id>  # one pack's odds, as the viewer shows them
    gen_pack_odds.py <booster_packs.json> --simulate N      # check the model against N packs per pack and
                                                            #   roll mode, made by the game's own algorithm
                                                            #   and RNG (needs numpy)
    gen_pack_odds.py --selftest                             # the chain maths against brute force

The model follows GeneratePackCards (booster_pack.c) step by step:
  1. The rarity roll is Random() % 180. It is % 270 when you picked this pack last time, and % 12 for the
     pity roll. It walks slots 0-6 and takes the first filled slot whose threshold is above the roll; if none
     is, the card comes from the commons.
  2. The rolled card is Random() % (the slot's size).
  3. The four commons are the first four of a copy of the commons slot, after 2N random transpositions
     (Random() % N twice for each), skipping copies of the rolled card.
Random() returns 15 bits, so each "% m" is weighted by how many of its 32768 values give each result.
After the transpositions, one card's position is a Markov chain, and so is the pair (card, rolled card).
Card c is picked if it ends in 0-3, or if it ends at 4 and the rolled card ends in 0-3. Propagating both
chains backwards gives that chance exactly, for every start position at once.
Stdlib only (except --simulate).
"""
import argparse
import itertools
import json
import sys

THRESHOLDS = [1, 3, 6, 10, 16, 28, 64, 180]     # 0x081A570C; slots 0-6 are walked
MODES = (180, 270, 12)                          # normal roll, same pack as last time, pity roll
MODE_NAMES = ("normal", "same pack again", "pity")
RAND_VALUES = 32768                             # Random() returns 0..0x7FFF
PICKS = 4                                       # commons after the rolled card

# The pick-a-pack screen's 23 packs (gPackInfo), with full names for the game's abbreviations.
FULL_NAMES = {
    1: "Vol.1", 2: "Vol.2", 3: "Vol.3", 4: "Vol.4", 5: "Vol.5", 6: "Vol.6", 7: "Vol.7",
    11: "Legend of Blue Eyes White Dragon",     # "LOBEWD"
    12: "Phantom God",                          # "Phantom of G"
    21: "Magic Ruler",                          # "MagicRuler"
    22: "Pharaoh's Servant",                    # "Pharao'sSurvant"
    23: "Curse of Anubis",                      # "CursrOfAnubis"
    33: "Premium Pack 3",                       # "Premium 3"
    41: "Ceremony",                             # "Celemony": the Ritual cards
    501: "Expert Pack 1", 502: "Expert Pack 2", 503: "Expert Pack 3", 504: "Duelist Pack",
    505: "The Final Duelist", 506: "Rare Selections", 507: "Expert Pack 4", 508: "Expert Pack 5",
    509: "Limited Collection",
}


def mod_weights(m):
    """P(Random() % m == k) for each k."""
    q, r = divmod(RAND_VALUES, m)
    return [(q + (k < r)) / RAND_VALUES for k in range(m)]


def common_slot(slots):
    """GetPackCommonSlot: the highest filled slot, 7 down to 1; 0 if none."""
    for i in range(7, 0, -1):
        if slots[i]:
            return i
    return 0


def slot_probs(slots, mod):
    """P(the rolled card comes from slot i), RollPackRarity with Random() % mod."""
    cs = common_slot(slots)
    probs = [0.0] * 8
    for roll, w in enumerate(mod_weights(mod)):
        for i in range(7):
            if roll < THRESHOLDS[i] and slots[i]:
                probs[i] += w
                break
        else:
            probs[cs] += w
    return probs


def single_chain(w, steps, end):
    """Backward pass of one card's position: start[p] = P(end condition | it starts at p)."""
    v = list(end)
    for _ in range(steps):
        dot = sum(wj * vj for wj, vj in zip(w, v))
        v = [(1 - 2 * wp * (1 - wp)) * vp + 2 * wp * (dot - wp * vp) for wp, vp in zip(w, v)]
    return v


def pair_chain(w, steps, end):
    """Backward pass of two cards' positions (p, q), p != q. A transposition {p, j} moves the first card to j
    (chance 2 w_p w_j), {q, j} moves the second, {p, q} swaps them; anything else leaves both."""
    n = len(w)
    v = [[0.0 if p == q else end(p, q) for q in range(n)] for p in range(n)]
    for _ in range(steps):
        col = [sum(w[j] * v[j][q] for j in range(n)) for q in range(n)]
        row = [sum(v[p][j] * w[j] for j in range(n)) for p in range(n)]
        new = [[0.0] * n for _ in range(n)]
        for p in range(n):
            wp, vp, rp, out = w[p], v[p], row[p], new[p]
            for q in range(n):
                if p == q:
                    continue
                wq, x = w[q], vp[q]
                rest = 1 - wp - wq
                stay = 1 - 2 * wp * wq - 2 * (wp + wq) * rest
                out[q] = (stay * x + 2 * wp * wq * v[q][p] + 2 * wp * (col[q] - wp * x)
                          + 2 * wq * (rp - wq * x))
        v = new
    return v


def pack_odds(pack):
    """{card number: [P(in the pack) for each mode]} for one pack, and P(the rolled card is rare) per mode."""
    slots = [[c for c, _ in s] for s in pack["slots"]]
    cs = common_slot(slots)
    pool = slots[cs]
    n = len(pool)
    if len(set(pool)) != n or n <= PICKS:
        sys.exit(f"pack {pack['id']}: the model needs {PICKS + 1}+ distinct commons")
    w = mod_weights(n)
    steps = 2 * n
    picked = single_chain(w, steps, [1.0 if p < PICKS else 0.0 for p in range(n)])
    # the rolled card sits at k: c is also picked from position PICKS when the rolled card ends before it
    joint = pair_chain(w, steps, lambda p, q: 1.0 if p == PICKS and q < PICKS else 0.0)
    cards = list(dict.fromkeys(c for s in slots for c in s))
    odds = {c: [] for c in cards}
    rare = []
    for mod in MODES:
        sp = slot_probs(slots, mod)
        first = dict.fromkeys(cards, 0.0)        # P(the rolled card is c)
        for i, s in enumerate(slots):
            for k, wk in enumerate(mod_weights(len(s)) if s else []):
                first[s[k]] += sp[i] * wk
        rare.append(1 - sp[cs])
        in_pool = sum(first[c] for c in pool)
        for c in cards:
            p = first[c]
            if c in pool:
                i = pool.index(c)
                p += (1 - in_pool) * picked[i]
                p += sum(first[f] * (picked[i] + joint[i][k]) for k, f in enumerate(pool) if k != i)
            odds[c].append(p)
        total = sum(o[-1] for o in odds.values())
        assert abs(total - (1 + PICKS)) < 1e-9, (pack["id"], mod, total)   # five different cards a pack
    return odds, rare


def rarest_slot(pack):
    return {c: i for i in reversed(range(8)) for c, _ in pack["slots"][i]}


def units(p):
    """0.01% steps, rounded."""
    return int(p * 10000 + 0.5)


def table(packs):
    out = ["/* Generated by gen_pack_odds.py from your booster_packs.json. It holds the game's card lists: never",
           " * commit it. Per card: number, rarest slot, chance of being in the pack in 0.01% (normal roll, same",
           " * pack as last time, pity roll). Per pack: id, cards, first card, commons slot, chance of a rare card",
           " * per roll, full name. */", "",
           f"#define PACKVIEW_PACK_COUNT {len(packs)}", "",
           "static const struct PackViewCard sPackViewCards[] = {"]
    rows = []
    first = 0
    for pack in packs:
        odds, rare = pack_odds(pack)
        slot = rarest_slot(pack)
        order = sorted(odds, key=lambda c: slot[c])        # rarest slot first, game order inside a slot
        out.append(f"    /* {pack['id']} {FULL_NAMES[pack['id']]} */")
        for c in order:
            out.append(f"    {{{c}, {slot[c]}, 0, {{{', '.join(str(units(p)) for p in odds[c])}}}}},")
        name = FULL_NAMES[pack["id"]].replace("\\", "\\\\").replace('"', '\\"')
        rows.append(f"    {{{pack['id']}, {len(order)}, {first}, {common_slot([s for s in pack['slots']])}, 0, "
                    f"{{{', '.join(str(units(p)) for p in rare)}}}, 0, \"{name}\"}},")
        first += len(order)
    out += ["};", "", "static const struct PackViewPack sPackViewPacks[PACKVIEW_PACK_COUNT] = {"] + rows + ["};", ""]
    return "\n".join(out)


def listed_packs(data):
    packs = [p for p in data["packs"] if p["id"] in FULL_NAMES]
    missing = set(FULL_NAMES) - {p["id"] for p in packs}
    if missing:
        sys.exit(f"booster_packs.json has no pack {sorted(missing)}")
    return packs


def show(pack):
    odds, rare = pack_odds(pack)
    slot = rarest_slot(pack)
    names = {c: n for s in pack["slots"] for c, n in s}
    print(f"{FULL_NAMES[pack['id']]} ({len(odds)} cards); a rare card: "
          + ", ".join(f"{m} {r * 100:.2f}%" for m, r in zip(MODE_NAMES, rare)))
    print(f"  {'card':34} slot  " + "  ".join(f"{m:>15}" for m in MODE_NAMES))
    for c in sorted(odds, key=lambda c: slot[c]):
        print(f"  {names[c]:34} {slot[c]:>4}  " + "  ".join(f"{p * 100:14.2f}%" for p in odds[c]))


# --- checks ---------------------------------------------------------------------------------------------

def brute_force(n, steps, w):
    """Exact distribution of the shuffled pool over all n! orders (small n)."""
    dist = {tuple(range(n)): 1.0}
    for _ in range(steps):
        new = {}
        for perm, pr in dist.items():
            for a in range(n):
                for b in range(n):
                    p = list(perm)
                    p[a], p[b] = p[b], p[a]
                    t = tuple(p)
                    new[t] = new.get(t, 0.0) + pr * w[a] * w[b]
        dist = new
    return dist


def selftest():
    for n, skew in ((5, 0.0), (6, 0.3)):
        w = [1 / n + skew * ((k % 2) - 0.5) / n for k in range(n)]   # an uneven Random() % n
        w = [x / sum(w) for x in w]
        steps = 2 * n
        dist = brute_force(n, steps, w)
        picked = single_chain(w, steps, [1.0 if p < PICKS else 0.0 for p in range(n)])
        joint = pair_chain(w, steps, lambda p, q: 1.0 if p == PICKS and q < PICKS else 0.0)
        worst = 0.0
        for i, k in itertools.permutations(range(n), 2):
            # perm[pos] = the card that started at index perm[pos]; where did cards i and k end?
            bf_pick = sum(pr for perm, pr in dist.items() if perm.index(i) < PICKS)
            bf_joint = sum(pr for perm, pr in dist.items() if perm.index(i) == PICKS and perm.index(k) < PICKS)
            worst = max(worst, abs(bf_pick - picked[i]), abs(bf_joint - joint[i][k]))
        print(f"n={n} skew={skew}: max |chain - brute force| = {worst:.2e}")
        assert worst < 1e-12
    print("selftest ok")


def simulate(packs, n, seed=1):
    """The game's GeneratePackCards with its Random(), on n independent RNG states at once."""
    import numpy as np
    gen = np.random.default_rng(seed)
    worst_z = worst_d = 0.0
    for pack in packs:
        slots = [[c for c, _ in s] for s in pack["slots"]]
        cs = common_slot(slots)
        pool0 = np.array(slots[cs], dtype=np.int64)
        size = len(pool0)
        odds, _ = pack_odds(pack)
        for mode, mod in enumerate(MODES):
            state = gen.integers(0, 2 ** 32, n, dtype=np.uint64)

            def rand():
                nonlocal state
                x = (state * 0x343FD + 0x269EC3) & 0xFFFFFFFF
                state = ((x << 16) | (x >> 16)) & 0xFFFFFFFF
                return ((state << 1) & 0xFFFFFFFF) >> 17

            roll = rand() % 180                        # RollPackRarity always draws this one first
            if mode == 1:
                roll = rand() % 270
            elif mode == 2:
                roll = rand() % 12
            slot = np.full(n, cs)
            for i in reversed(range(7)):
                if slots[i]:
                    slot = np.where(roll < THRESHOLDS[i], i, slot)
            width = max(len(s) for s in slots)
            mat = np.array([s + [0] * (width - len(s)) for s in slots], dtype=np.int64)
            count = np.array([max(len(s), 1) for s in slots], dtype=np.uint64)
            first = mat[slot, (rand() % count[slot]).astype(np.int64)]
            pool = np.tile(pool0, (n, 1))
            rows = np.arange(n)
            for _ in range(2 * size):
                a = (rand() % size).astype(np.int64)
                b = (rand() % size).astype(np.int64)
                pa = pool[rows, a].copy()
                pool[rows, a] = pool[rows, b]
                pool[rows, b] = pa
            keep = pool != first[:, None]
            take = keep & (np.cumsum(keep, axis=1) <= PICKS)
            got = {}
            for c in odds:
                got[c] = int(((pool == c) & take).sum() + (first == c).sum()) / n
            for c, row in odds.items():
                p = row[mode]
                d = got[c] - p
                se = max((p * (1 - p) / n) ** 0.5, 1 / n)
                worst_z = max(worst_z, abs(d) / se)
                worst_d = max(worst_d, abs(d))
        print(f"{pack['id']:>4} {FULL_NAMES[pack['id']]:32} done; so far max |sim - model| = "
              f"{worst_d * 100:.3f} points, max |z| = {worst_z:.2f}", flush=True)
    cards = sum(len(pack_odds(p)[0]) for p in packs) * len(MODES)
    print(f"{cards} card odds, {n} packs each: max |sim - model| = {worst_d * 100:.3f} points, "
          f"max |z| = {worst_z:.2f}")
    return worst_z


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--show", type=int, metavar="PACK_ID")
    ap.add_argument("--simulate", type=int, metavar="N")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.json:
        ap.error("booster_packs.json is needed")
    with open(a.json) as f:
        packs = listed_packs(json.load(f))
    if a.show is not None:
        show(next(p for p in packs if p["id"] == a.show))
    elif a.simulate:
        z = simulate(packs, a.simulate)
        sys.exit(0 if z < 5.5 else 1)
    elif a.out:
        text = table(packs)
        try:
            with open(a.out) as f:
                if f.read() == text:
                    return
        except FileNotFoundError:
            pass
        with open(a.out, "w") as f:
            f.write(text)
    else:
        ap.error("give <out.h>, --show or --simulate")


if __name__ == "__main__":
    main()
