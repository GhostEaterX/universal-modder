#!/usr/bin/env python3
"""Make the Egyptian Gods need three Tributes (TCG rule). Run after patch_source.py on eds-decomp 857002a.

    python3 patch_three_tributes.py <eds-decomp checkout> [--check]

Every other monster keeps EDS's rules: no Tribute at levels 1-4, one at 5-6, two at 7+. The engine already
has unused room for a third Tribute: SummonAction.tribute3Zone / hasTribute3, whose owner bit this puts in
the free bit 30, and the Special-Summon-from-hand step already Tributes it. These edits fill in the rest:
  - the Tribute word that the summon queues decode gets a third byte (bits 16-23, the same zone | owner << 4
    | present << 7 format); every queue always sets the third Tribute, so a stale one never leaks;
  - the Normal Summon executors Tribute the third monster;
  - the summon check wants three tributable monsters for a God;
  - the player's card menu asks "requires 3 Tributes" and takes three picks; B goes back to the question;
  - Ultimate Offering's extra Normal Summon takes three picks for a God too;
  - the CPU (AiHasTributesFor, AiChooseSummonWithTribute, both AiStepMainPhase paths) picks three, using a
    new AiPickTributeMonsterExcept that skips two zones.
The edits are anchored on short strings of the pinned decomp; the code they add is this mod's own.
Idempotent. Stdlib only.
"""
import argparse
import sys
from pathlib import Path

MARK = "mod: three Tributes"

THIRD_FROM_WORD = """    {{   /* {mark}: the third Tribute byte, bits 16-23 of the word (0 when there is none) */
        u8 third = (u32){word} >> 16;
        gSummonAction.tribute3Zone = third & 7;
        gSummonAction.tribute3Player = (third >> 4) & 1;
        gSummonAction.hasTribute3 = third >> 7;
    }}
"""

PICK_THREE_AI = """{indent}int t1 = AiPickTributeMonster(-1, 0);
{indent}int t2 = t1 == -1 ? -1 : AiPickTributeMonster(t1, 0);
{indent}int t3 = t2 == -1 ? -1 : AiPickTributeMonsterExcept(t1, t2);
"""
PICK_THREE_AI_20 = PICK_THREE_AI.format(indent=" " * 20)
PICK_THREE_AI_12 = PICK_THREE_AI.format(indent=" " * 12)

EDITS = [
    # ---- shared definitions ----
    ("include/constants/cards.h",
     "\n#endif /* GUARD_CONSTANTS_CARDS_H */",
     """
/* Mod (playable Egyptian Gods): Obelisk, Slifer and Ra by card number. They need three Tributes. */
#define IS_EGYPTIAN_GOD(number) \\
    ((u32)((number) - CARD_OBELISK_THE_TORMENTOR) <= CARD_THE_WINGED_DRAGON_OF_RA - CARD_OBELISK_THE_TORMENTOR)

#endif /* GUARD_CONSTANTS_CARDS_H */""", "replace"),
    ("include/summon.h",
     "    u32 unk0_30:1;              /* bit 30 */",
     "    u32 tribute3Player:1;       /* bit 30: owner of the third tribute (mod: three Tributes) */", "replace"),
    ("include/summon.h",
     "void QueueNormalSummonChoosePosition(int player, int handIndex, int zone, u16 tributes);\n",
     "/* Mod: the same with a three-byte Tribute word (the Egyptian Gods). */\n"
     "void QueueNormalSummonChoosePositionEx(int player, int handIndex, int zone, int tributes);\n", "after"),
    ("include/ai.h",
     "int AiPickTributeMonster(int excludeZone, u16 allowFusion);\n",
     "/* Mod: AiPickTributeMonster that skips two zones, for an Egyptian God's third tribute. */\n"
     "int AiPickTributeMonsterExcept(int excludeZone, int excludeZone2);\n", "after"),

    # ---- queues: decode the third byte ----
    ("src/summon_action.c",
     """        gSummonAction.hasTribute2 = 0;
        action = &gSummonAction;
    }
    {
        struct SummonAction *record = action;
""",
     THIRD_FROM_WORD.format(mark=MARK, word="tributes"), "before:    {\n        struct SummonAction *record = action;\n"),
    ("src/summon_action.c",
     "void QueueNormalSummonChoosePosition(int player, int handIndex, int zone, u16 tributes)\n{",
     """/* Mod: the original entry point, for the callers with a two-byte Tribute word. */
void QueueNormalSummonChoosePosition(int player, int handIndex, int zone, u16 tributes)
{
    QueueNormalSummonChoosePositionEx(player, handIndex, zone, tributes);
}

void QueueNormalSummonChoosePositionEx(int player, int handIndex, int zone, int tributes)
{""", "replace"),
    ("src/summon_action.c",
     """        gSummonAction.hasTribute2 = 0;
        action = &gSummonAction;
    }
    action->cardId = DUEL_CARD_ID(""",
     THIRD_FROM_WORD.format(mark=MARK, word="tributes"), "before:    action->cardId = DUEL_CARD_ID("),
    ("src/summon_builders.c",
     """        gSummonAction.hasTribute2 = 0;
    }
    gSummonAction.cardId = CARD_ID(*(u32 *)((player & 1) * PLAYER_STRIDE + handIndex * 4 + (u32)gDuelHands));
    gSummonAction.kind = SUMMON_ACTION_SPECIAL_FROM_HAND;""",
     THIRD_FROM_WORD.format(mark=MARK, word="tributes"), "before:    gSummonAction.cardId = CARD_ID("),

    # ---- executors: Tribute the third monster ----
    ("src/summon_checks.c",
     """        if (gSummonAction.hasTribute2)
            TributeMonster(gSummonAction.tribute2Player, gSummonAction.tribute2Zone);
""",
     f"""        if (gSummonAction.hasTribute3)      /* {MARK} */
            TributeMonster(gSummonAction.tribute3Player, gSummonAction.tribute3Zone);
""", "after"),
    ("src/summon_checks.c",
     """        if (action->hasTribute2)
            TributeMonster(action->player, action->tribute2Zone);
""",
     f"""        if (action->hasTribute3)            /* {MARK} */
            TributeMonster(action->player, action->tribute3Zone);
""", "after"),

    # ---- the summon check ----
    ("src/summon_checks.c",
     """    default:
        level = GetCardLevel(cardId);
""",
     f"""    default:
        if (IS_EGYPTIAN_GOD(number))        /* {MARK} */
            return CountTributableMonsters(player, -1) > 2;
        level = GetCardLevel(cardId);
""", "replace"),

    # ---- the CPU ----
    ("src/summon_builders.c",
     "/*\n * 1 if player 1 has enough monsters to tribute for the card:",
     f"""/* Mod (three Tributes): AiPickTributeMonster with two excluded zones, for an Egyptian God's third tribute. */
int AiPickTributeMonsterExcept(int excludeZone, int excludeZone2)
{{
    int i;
    int best = 32000;
    int bestZone = -1;

    for (i = 0; i < MONSTER_ZONE_COUNT; i++) {{
        u16 id = CARD_ID(ZONE1_WORD(i));
        if (id != 0 && i != excludeZone && i != excludeZone2 && CARD_NUMBER(id) == CARD_SANGAN)
            return i;
    }}
    for (i = 0; i < MONSTER_ZONE_COUNT; i++) {{
        u16 id = CARD_ID(ZONE1_WORD(i));
        if (id != 0 && i != excludeZone && i != excludeZone2 && CARD_NUMBER(id) == CARD_WITCH_OF_THE_BLACK_FOREST)
            return i;
    }}
    for (i = 0; i < MONSTER_ZONE_COUNT; i++) {{
        u16 id = CARD_ID(ZONE1_WORD(i));
        if (id != 0 && i != excludeZone && i != excludeZone2 && !IsFusionMonster(id)) {{
            struct ZoneCardStats stats;
            int value;

            GetZoneCardStats(1, i, &stats);
            value = stats.atk * 2 + stats.def;
            if (value < best) {{
                bestZone = i;
                best = value;
            }}
        }}
    }}
    return bestZone;
}}

""", "before:/*\n * 1 if player 1 has enough monsters to tribute for the card:"),
    ("src/summon_builders.c",
     """    CARD_LEVEL(cardId, level);
    if (level < 0)""",
     f"""    if (IS_EGYPTIAN_GOD(CARD_NUMBER(cardId))) {{     /* {MARK}, all different */
        first = AiPickTributeMonster(-1, 0);
        if (first == -1)
            return 0;
        second = AiPickTributeMonster(first, 0);
        if (second == -1)
            return 0;
        return AiPickTributeMonsterExcept(first, second) != -1;
    }}
""", "before:    CARD_LEVEL(cardId, level);\n    if (level < 0)"),
    ("src/ai_summon.c",
     """        tributeMask = 0;
        switch ((int)CardLevel(cardId)) {""",
     f"""        tributeMask = 0;
        if (IS_EGYPTIAN_GOD(CARD_NUMBER(cardId))) {{     /* {MARK}: one nibble each, zone | 8 */
            int tribute3 = -1;
            tribute1 = AiPickTributeMonster(-1, 0);
            tribute2 = tribute1 == -1 ? -1 : AiPickTributeMonster(tribute1, 0);
            if (tribute2 != -1)
                tribute3 = AiPickTributeMonsterExcept(tribute1, tribute2);
            if (tribute3 == -1)
                skip = 1;
            tributeMask = ((tribute1 | 8) << 8) | ((tribute2 | 8) << 4) | (tribute3 | 8);
        }} else
        switch ((int)CardLevel(cardId)) {{""", "replace"),
    ("src/ai_steps.c",
     """                switch (cost) {
                case 0:
                    break;""",
     f"""                if (IS_EGYPTIAN_GOD(*numPtr)) {{     /* {MARK} */
{PICK_THREE_AI_20}                    if (t3 != -1) {{
                        QueueNormalSummon(1, handIdx, t1,
                                          (0x90 | t1) | ((0x90 | t2) << 8) | ((0x90 | t3) << 16), hasFlip2 == 0);
                        return 1;
                    }}
                    gAiState.phase++;
                    return 0;
                }}
""", "before:                switch (cost) {\n                case 0:\n                    break;"),
    ("src/ai_steps.c",
     """        id = CARD_ID(gDuelPlayers.hand1[handIdx]);
        switch (CardCost(id)) {""",
     f"""        id = CARD_ID(gDuelPlayers.hand1[handIdx]);
        if (IS_EGYPTIAN_GOD(gCardIdToNumber[id & CARD_ID_MASK])) {{     /* {MARK} */
{PICK_THREE_AI_12}            if (t3 != -1)
                QueueNormalSummon(1, handIdx, t1, (0x90 | t1) | ((0x90 | t2) << 8) | ((0x90 | t3) << 16), 1);
            gAiState.phase = AI_MAIN_RESET;
            return 0;
        }}
        switch (CardCost(id)) {{""", "replace"),

    # ---- the player's card menu ----
    ("src/effect_hooks.c",
     "    SUMMON_STEP_KEY_1257_SUMMON = 84,\n",
     f"""    SUMMON_STEP_THREE_TRIBUTES_ASK = 90,    /* {MARK} (the Egyptian Gods): answer of "3 Tributes?" */
    SUMMON_STEP_THREE_TRIBUTES_PROMPT_1 = 91,
    SUMMON_STEP_THREE_TRIBUTES_PICK_1 = 92,
    SUMMON_STEP_THREE_TRIBUTES_PROMPT_2 = 93,
    SUMMON_STEP_THREE_TRIBUTES_PICK_2 = 94,
    SUMMON_STEP_THREE_TRIBUTES_PROMPT_3 = 95,
    SUMMON_STEP_THREE_TRIBUTES_PICK_3 = 96,  /* the third pick waits in summonSeq: zone | owner << 3 */
    SUMMON_STEP_THREE_TRIBUTES_SUMMON = 97,
""", "after"),
    ("src/effect_hooks.c",
     "#define TRIBUTE_TWO     0x8080\n",
     f"""
/* Mod (three Tributes): the Egyptian Gods' prompts, in the style of gTributeSummonPrompts. Ultimate Offering
 * (effect_resolve4.c) uses them too. The third Tribute is byte 2 of the Tribute word. */
const char gStrThreeTributesPrompt[] = "Summoning this monster requires @33 @0Tributes. Do you wish to @2Summon@0?";
const char gStrSelectThirdTribute[] = "Please select 3rd monster as @3Tribute@0.";
#define TRIBUTE_THIRD_SHIFT 16
""", "after"),
    ("src/effect_hooks.c",
     "        default:\n        normal_summon:\n",
     f"""            if (IS_EGYPTIAN_GOD(CARD_NUMBER(CM.cardMenuCard))) {{     /* {MARK} */
                OPEN_PROMPT(gStrThreeTributesPrompt);
                TextBoxSetMenu(TEXTBOX_MENU_YES_NO, 0, 0);
                CM.summonTributes = 0;
                CM.summonSeq = 0;
                CM.step = SUMMON_STEP_THREE_TRIBUTES_ASK;
                break;
            }}
""", "after"),
    ("src/effect_hooks.c",
     "    /* ---- One Tribute (level 5-6) ---- */\n",
     f"""    /* ---- {MARK} (the Egyptian Gods): picks 1-2 as in the two-Tribute steps, the third in summonSeq ---- */
    case SUMMON_STEP_THREE_TRIBUTES_ASK:
        if (gTextBox.result == 0) {{         /* answered No: cancel */
            CM.confirmed = 0;
            break;
        }}
        CM.step = SUMMON_STEP_THREE_TRIBUTES_PROMPT_1;
        /* fall through */
    case SUMMON_STEP_THREE_TRIBUTES_PROMPT_1:
    case SUMMON_STEP_THREE_TRIBUTES_PROMPT_2:
    case SUMMON_STEP_THREE_TRIBUTES_PROMPT_3:
        if (CM.step == SUMMON_STEP_THREE_TRIBUTES_PROMPT_1)
            OPEN_MESSAGE(gTributeSummonPrompts[TRIBUTE_PROMPT_SELECT_FIRST]);
        else if (CM.step == SUMMON_STEP_THREE_TRIBUTES_PROMPT_2)
            OPEN_MESSAGE(gTributeSummonPrompts[TRIBUTE_PROMPT_SELECT_SECOND]);
        else
            OPEN_MESSAGE(gStrSelectThirdTribute);
        CM.step++;
        break;
    case SUMMON_STEP_THREE_TRIBUTES_PICK_1:
    case SUMMON_STEP_THREE_TRIBUTES_PICK_2:
    case SUMMON_STEP_THREE_TRIBUTES_PICK_3:
        if (gMain.newKeys & B_BUTTON) {{     /* back to the question; the picks are dropped */
            OPEN_PROMPT(gStrThreeTributesPrompt);
            TextBoxSetMenu(TEXTBOX_MENU_YES_NO, 0, 0);
            CM.summonTributes = 0;
            CM.summonSeq = 0;
            CM.step = SUMMON_STEP_THREE_TRIBUTES_ASK;
        }} else if (DuelCursor_PickTarget(PICK_ANY_MONSTER)) {{
            u32 pick = ((u8)gDuelScreen.selIndex & 7) | (((u8)gDuelScreen.selPlayer & 1) << 4);
            int picked = (CM.step - SUMMON_STEP_THREE_TRIBUTES_PICK_1) / 2;     /* picks so far: 0-2 */

            if (IsTributableMonsterInt(gDuelScreen.selPlayer, gDuelScreen.selIndex)
                && (picked < 1 || pick != (u8)CM.summonTributes)
                && (picked < 2 || pick != (u8)(CM.summonTributes >> 8))) {{
                PlaySE(SE_CONFIRM);
                POINT_AT_PICKED_CARD();
                if (picked == 0)
                    CM.summonTributes = pick;
                else if (picked == 1)
                    CM.summonTributes = (u8)CM.summonTributes | (pick << 8);
                else
                    CM.summonSeq = (pick & 7) | ((pick >> 4) << 3);
                CM.step++;
            }} else {{
                PlaySE(SE_ERROR);
            }}
        }}
        break;
    case SUMMON_STEP_THREE_TRIBUTES_SUMMON: {{
        u32 third = (CM.summonSeq & 7) | (((CM.summonSeq >> 3) & 1) << 4) | 0x80;
        int tributes = CM.summonTributes | TRIBUTE_TWO | (third << TRIBUTE_THIRD_SHIFT);

        if (special)
            QueueSpecialSummonFromHand(CM.player, CM.index, CM.summonTributes & 7, tributes, faceUp);
        else
            QueueNormalSummon(CM.player, CM.index, CM.summonTributes & 7, tributes, faceUp);
        CM.summonSeq = 0;
        CM.confirmed = 0;
        break;
    }}

""", "before:    /* ---- One Tribute (level 5-6) ---- */\n"),

    # ---- Ultimate Offering ----
    ("src/effect_resolve4.c",
     "    OFFERING_STEP_ASK_TWO = 0x78,",
     f"""    OFFERING_STEP_ASK_THREE = 0x7A,         /* {MARK}: an Egyptian God: "requires 3 Tributes. Summon?" */
    OFFERING_STEP_ANSWER_THREE = 0x79,      /* No: back to OFFERING_STEP_START; Yes: the first pick */
    OFFERING_STEP_PROMPT_THIRD = 0x73,      /* after the second pick, for a God */
    OFFERING_STEP_PICK_THIRD = 0x72,        /* the third pick goes in the high byte of targets[1] */
    OFFERING_STEP_ASK_TWO = 0x78,""", "replace"),
    ("src/effect_resolve4.c",
     "int EffectUltimateOfferingResolve(struct ChainEntry *link)\n{",
     f"""/* Mod (three Tributes): the Egyptian Gods' prompts (effect_hooks.c). */
extern const char gStrThreeTributesPrompt[];
extern const char gStrSelectThirdTribute[];

/* Mod: 1 if the hand card that Ultimate Offering is summoning (targets[0]) is an Egyptian God. */
static int OfferingSummonsGod(struct ChainEntry *link)
{{
    u16 id = CARD_ID(CARD_WORD(gDuelPlayers[link->player & 1].hand[link->targets[0]]));
    return IS_EGYPTIAN_GOD(CARD_NUMBER(id));
}}

int EffectUltimateOfferingResolve(struct ChainEntry *link)
{{""", "replace"),
    ("src/effect_resolve4.c",
     """                    switch (level) {
                    case 1:
                    case 2:
                    case 3:
                    case 4:
                        link->targets[1] = FindFreeMonsterZone(link->player);""",
     f"""                    if (IS_EGYPTIAN_GOD(CARD_NUMBER(id)))     /* {MARK} */
                        return OFFERING_STEP_ASK_THREE;
""", "before:                    switch (level) {\n                    case 1:"),
    ("src/effect_resolve4.c",
     "        case OFFERING_STEP_ASK_TWO:\n",
     f"""        case OFFERING_STEP_ASK_THREE:       /* {MARK} */
            TextBoxOpen(PROMPT_POS, PROMPT_SIZE, TEXTBOX_FLAGS_DEFAULT, (const u8 *)gStrThreeTributesPrompt);
            TextBoxSetMenu(TEXTBOX_MENU_YES_NO, NULL, NULL);
            return OFFERING_STEP_ANSWER_THREE;
        case OFFERING_STEP_ANSWER_THREE:
            if (gTextBox.result == 0)
                return OFFERING_STEP_START;
            TextBoxOpen(PROMPT_POS, PICK_PROMPT_SIZE, TEXTBOX_FLAGS_DEFAULT, gTributeSummonPrompts[2]);
            return OFFERING_STEP_PICK_FIRST;
        case OFFERING_STEP_PROMPT_THIRD:
            TextBoxOpen(PROMPT_POS, PICK_PROMPT_SIZE, TEXTBOX_FLAGS_DEFAULT, (const u8 *)gStrSelectThirdTribute);
            return OFFERING_STEP_PICK_THIRD;
        case OFFERING_STEP_PICK_THIRD:
            if (DuelCursor_PickTarget(PICK_ANY_MONSTER) != 0) {{
                if (IsTributableMonsterInt(gDuelScreen.selPlayer, gDuelScreen.selIndex) != 0
                    && gDuelScreen.selIndex != (u8)link->targets[1]
                    && gDuelScreen.selIndex != (link->targets[2] & 7)) {{
                    PlaySE(SE_CONFIRM);
                    DuelCmd_Push(DUEL_CMD_POINT_AT_CARD, (u16)gDuelScreen.selPlayer, CURSOR_AREA_INDEX, 0);
                    link->targets[1] = (u8)link->targets[1] | ((u8)((int)gDuelScreen.selIndex | TRIBUTE_ZONE_SET) << 8);
                    return OFFERING_STEP_SUMMON;
                }}
                PlaySE(SE_ERROR);
            }}
            return OFFERING_STEP_PICK_THIRD;
""", "before:        case OFFERING_STEP_ASK_TWO:\n"),
    ("src/effect_resolve4.c",
     """                    link->targets[2] = (u8)((int)gDuelScreen.selIndex | TRIBUTE_ZONE_SET) | link->targets[2];
                    return OFFERING_STEP_SUMMON;""",
     f"""                    link->targets[2] = (u8)((int)gDuelScreen.selIndex | TRIBUTE_ZONE_SET) | link->targets[2];
                    if (OfferingSummonsGod(link))       /* {MARK} */
                        return OFFERING_STEP_PROMPT_THIRD;
                    return OFFERING_STEP_SUMMON;""", "replace"),
    ("src/effect_resolve4.c",
     "            QueueNormalSummonChoosePosition(link->player, link->targets[0], link->targets[1], link->targets[2]);\n",
     f"""            /* {MARK}: a God's third pick rides in the high byte of targets[1] */
            QueueNormalSummonChoosePositionEx(link->player, link->targets[0], (u8)link->targets[1],
                                              link->targets[2] | ((u32)(link->targets[1] >> 8) << 16));
""", "replace"),
]


def apply(root, check):
    changed = 0
    texts = {}
    for path, anchor, text, how in EDITS:
        p = root / path
        t = texts.get(p, p.read_text())
        if how == "after":
            new = anchor + text
        elif how == "replace":
            new = text
        else:   # "before:<where>": insert `text` before <where>, which must be inside the anchor
            where = how[len("before:"):]
            assert where in anchor, (path, where[:40])
            new = anchor.replace(where, text + where, 1)
        if new in t:
            continue
        if t.count(anchor) != 1:
            sys.exit(f"{path}: anchor found {t.count(anchor)} times (not eds-decomp 857002a + patch_source.py?):\n"
                     f"{anchor[:120]}")
        texts[p] = t.replace(anchor, new)
        changed += 1
    if not check:
        for p, t in texts.items():
            p.write_text(t)
    return changed, len(texts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("decomp", type=Path)
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()
    root = args.decomp
    if "CARD_TYPE_IS_MONSTER" not in (root / "include/constants/card_stats.h").read_text():
        sys.exit("run patch_source.py first")
    n, files = apply(root, args.check)
    print(f"{'would apply' if args.check else 'applied'} {n} of {len(EDITS)} edits in {files} files"
          + (" (already applied)" if n == 0 else ""))


if __name__ == "__main__":
    main()
