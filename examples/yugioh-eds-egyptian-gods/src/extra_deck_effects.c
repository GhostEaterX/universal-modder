#include "global.h"
#include "card_data.h"              /* gCardIdToNumber, CARD_ID_MASK */
#include "constants/card_stats.h"   /* ATTRIBUTE_* */
#include "constants/cards.h"        /* CARD_* card numbers */
#include "constants/duel.h"         /* ZONE_*, PHASE_*, PICK_*, CHAIN_KIND_MONSTER, ZONE_LINK_CARD_EFFECT */
#include "constants/duel_cmds.h"    /* DUEL_CMD_*, DUEL_CMD_PLAYER */
#include "constants/sound.h"        /* SE_ERROR */
#include "duel.h"                   /* gDuel, gDuelPlayers, GetZoneCardAtk, CountMonsters */
#include "chain.h"                  /* struct ChainEntry, gChain, Chain_AddPending */
#include "duel_cmd.h"               /* DuelCmd_Push */
#include "duel_actions.h"           /* QueueRemoveZoneLink, ChangeBattlePosition */
#include "duel_screen.h"            /* gDuelScreen, DuelCursor_PickTarget */
#include "effect.h"                 /* struct CardEffect, gCardEffectsMod, CanActivateEffect, TryAddEffectTarget */
#include "effect_handlers.h"        /* the original handlers these rows reuse */
#include "text_box.h"               /* TextBoxOpen */
#include "sound.h"                  /* PlaySE */
#include "gba.h"                    /* B_BUTTON */
#include "main.h"                   /* gMain.newKeys */
#include "ai.h"                     /* AiCanChangePosition */
#include "god_effects.h"            /* GOD_EFFECT_ROWS */
#include "boss_effects.h"           /* BOSS_EFFECT_ROWS, BossFindCardEffect */
#include "extra_deck_effects.h"

/*
 * Extra Deck effects (universal-modder), in the three-Tribute effects build only.
 *
 * A Fusion monster costs Polymerization and two cards, a Ritual monster its Ritual Magic card and Tributes worth
 * its Level, and most of the Level 7+ ones still have no effect and less ATK than a two-Tribute Normal monster.
 * So each one that falls short of what its summon costs gets an effect the engine already runs for another card,
 * which the CPU uses too:
 *
 *   B. Skull Dragon, Black Luster Soldier, Javelin Beetle    piercing battle damage (Summoned Skull's, this mod)
 *   Labyrinth Tank, Crab Turtle, Fortress Whale               not destroyed by battle (Millennium Golem's)
 *   Twin-Headed Thunder Dragon   +300 ATK in its controller's Battle Phase (the rule of effect key 1516)
 *   Skull Knight, Zera The Mant, Dokurorider    +100 ATK per monster in their controller's Graveyard (Shadow
 *                                               Ghoul's); Chakra counts both Graveyards
 *   Kaiser Dragon     +1000 ATK in a battle with a DARK monster (Insect Soldiers of the Sky's, against WIND)
 *   Garma Sword       a LIGHT monster it battles is destroyed (Mechanical Spider's, against DARK)
 *   Magician of Black Chaos   Dark Magician's once-per-turn Spell/Trap destroy (this mod)
 *   Thousand Dragon   Goddess of Whim's once-per-turn coin: ATK doubled or halved until the end of the turn
 *   Bickuribox        Dream Clown's trigger: changed to Defense Position, it destroys 1 monster (the CPU makes
 *                     the change itself when the human has a stronger monster)
 *   Skull Guardian    Suijin's answer to an attack (its ATK becomes 0), once per turn
 *   Gaia the Dragon Champion, Super War-Lion   once per turn, in Main Phase 1: destroy 1 face-up monster the
 *                     opponent controls with less ATK; then it can't attack that turn (Obelisk's lock)
 *
 * The stat and battle-list effects are edits of the engine's own switches (patch_extra_deck_effects.py); this
 * unit holds the rest. As in boss_effects.c, the table rows only point at functions of the new code.
 */

#define NUMBER_OF(id)       (gCardIdToNumber[(id) & CARD_ID_MASK])
#define CMD(player, cmd)    ((player) ? DUEL_CMD_PLAYER | (cmd) : (cmd))
#define ZONE(player, zone)  (&gDuelPlayers[(player) & 1].zones[(zone)])
#define LOC(player, zone)   ((u8)(player) | (u16)((u8)(zone) << 8))
#define KAISER_BONUS        1000

extern const u8 gStrDesignateOpponentMonsterCardToDestroy[];   /* Dream Clown's and Barrel Dragon's prompt */

int ExtraDeckFindCardEffect(u16 number)
{
    int i = BossFindCardEffect(number);

    if (i >= 0)
        return i;
    for (i = GOD_EFFECT_ROWS + BOSS_EFFECT_ROWS; i < GOD_EFFECT_ROWS + BOSS_EFFECT_ROWS + EXTRA_DECK_EFFECT_ROWS; i++) {
        if (gCardEffectsMod[i].number == number)
            return i;
    }
    return -1;
}

int ExtraDeckPierces(u16 cardId)
{
    switch (NUMBER_OF(cardId)) {
    case CARD_B_SKULL_DRAGON:
    case CARD_BLACK_LUSTER_SOLDIER:
    case CARD_JAVELIN_BEETLE:
        return 1;
    }
    return 0;
}

int ExtraDeckBattleIndestructible(u16 cardId)
{
    switch (NUMBER_OF(cardId)) {
    case CARD_LABYRINTH_TANK:
    case CARD_CRAB_TURTLE:
    case CARD_FORTRESS_WHALE:
        return 1;
    }
    return 0;
}

int ExtraDeckBattleAtkBonus(u16 cardId, int foeAttribute)
{
    if (NUMBER_OF(cardId) == CARD_KAISER_DRAGON && foeAttribute == ATTRIBUTE_DARK)
        return KAISER_BONUS;
    return 0;
}

int ExtraDeckDestroysLight(u16 cardId)
{
    return NUMBER_OF(cardId) == CARD_GARMA_SWORD;
}

/* The coin's link holds the card ID of the Thousand Dragon that tossed it (either art); the removal matches it
 * exactly, so each link is removed by its own ID. */
void ExtraDeckEndOfTurnLinks(int player, int zone)
{
    struct DuelZone *z = ZONE(player, zone);
    int i;

    for (i = 0; i < z->numLinks; i++) {
        u16 link = z->links[i];

        if ((u8)z->linkKinds[i] == ZONE_LINK_CARD_EFFECT
            && (NUMBER_OF(link) == CARD_THOUSAND_DRAGON || NUMBER_OF(link) == CARD_THOUSAND_DRAGON_ALT))
            QueueRemoveZoneLink(player, link, LOC(player, zone), ZONE_LINK_CARD_EFFECT);
    }
}

/* ---- Gaia the Dragon Champion and Super War-Lion ---------------------------------------------------------- */

/* Main Phase 1 of its controller's turn only, so it can't attack first and use the effect after. */
int ExtraDeckChampionPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand)
{
    if (card->player != gDuel.turnPlayer || gDuel.phase != PHASE_MAIN1)
        return 0;
    return EffectOncePerTurnPrepare(card, (int)chainLink, fromHand);
}

/* A face-up monster of the opponent with less ATK than the activating monster, that the effect can target. */
u16 ExtraDeckChampionCheck(struct ChainEntry *card, u16 pos)
{
    int player = (u8)pos;
    int zone = pos >> 8;
    struct DuelZone *z;

    if (player == card->player || zone > ZONE_MONSTER_4)
        return 0;
    z = ZONE(player, zone);
    if (!z->card.id || !z->isFaceUp || !CanCardTargetZone(card->card, player, zone))
        return 0;
    return GetZoneCardAtk(player, zone) < GetZoneCardAtk(card->player, card->zone);
}

/* The CPU's target: the human's strongest monster (by ATK) that the check accepts, or -1. */
static int ChampionAiTarget(struct ChainEntry *card)
{
    int zone, best = -1;
    u32 bestAtk = 0;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        if (ExtraDeckChampionCheck(card, LOC(0, zone)) && (best < 0 || GetZoneCardAtk(0, zone) > bestAtk)) {
            best = zone;
            bestAtk = GetZoneCardAtk(0, zone);
        }
    }
    return best;
}

/* The human picks one of the CPU's face-up monsters with less ATK, with Dream Clown's "destroy" prompt; the CPU
 * takes ChampionAiTarget's. */
int ExtraDeckChampionChainB(struct ChainEntry *link, struct ChainEntry *prevLink)
{
    if (link->player) {
        int zone = ChampionAiTarget(link);

        link->numTargets = 0;
        if (zone >= 0)
            TryAddEffectTarget(link, 0, zone);
        return 1;
    }
    if (gChain.targetStep == 0) {
        link->numTargets = 0;
        TextBoxOpen(TARGET_PROMPT_POS, TARGET_PROMPT_SIZE, TEXTBOX_FLAGS_DEFAULT,
                    gStrDesignateOpponentMonsterCardToDestroy);
        gChain.targetStep++;
    } else if (gMain.newKeys & B_BUTTON) {
        gChain.targetStep = 0;
    } else if (DuelCursor_PickTarget(PICK_PLAYER1(PICK_FACE_UP_MONSTER_ANY))) {
        int player = gDuelScreen.selPlayer;
        int zone = gDuelScreen.selArea + gDuelScreen.selIndex;

        if (ExtraDeckChampionCheck(link, LOC(player, zone)) && TryAddEffectTarget(link, player, zone))
            return 1;
        PlaySE(SE_ERROR);
    }
    return 0;
}

/* Destroy the target (Dream Clown's resolve); the monster can't attack this turn (Obelisk's lock, lifted at the
 * start of the next turn) and its effect is used up. */
int ExtraDeckChampionResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    if (!link->negated) {
        struct DuelZone *self = ZONE(link->player, link->zone);

        EffectDestroyTargetResolve(link);
        if (self->card.id && NUMBER_OF(self->card.id) == NUMBER_OF(link->card))
            DuelCmd_Push(CMD(link->player, DUEL_CMD_SET_CANNOT_ATTACK), link->zone, 1, 0);
        DuelCmd_Push(CMD(link->player, DUEL_CMD_SET_EFFECT_UNUSED), link->zone, 0, 0);
    }
    return EFFECT_STEP_DONE;
}

/* ---- Thousand Dragon and Bickuribox ------------------------------------------------------------------------- */

/* Goddess of Whim's steps: the call (the human picks, the CPU at random), the toss and the link that doubles or
 * halves ATK (card_stats.c), then the effect is used up. */
int ExtraDeckThousandDragonResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    return EffectGoddessOfWhimResolve(link);
}

/* Dream Clown's resolve. */
int ExtraDeckDestroyTargetResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    return EffectDestroyTargetResolve(link);
}

/* ---- The CPU ------------------------------------------------------------------------------------------------ */

/* The CPU's face-up Attack Position Bickuribox goes to Defense Position, as the human's menu does it, when the
 * human controls a face-up monster at least as strong (so it would not attack anyway) that its trigger can
 * destroy. The original AI never moves a monster from Attack to Defense Position, so Dream Clown never triggers
 * for it. */
static int BickuriboxAiSwitch(struct ChainEntry *ref)
{
    struct DuelZone *z = ZONE(1, ref->zone);
    u32 atk = GetZoneCardAtk(1, ref->zone);
    int zone;

    if (z->isDefense || !AiCanChangePosition(1, ref->zone) || gDuelPlayers[1].positionChangeLocked
        || CountActiveCardsOnField(0, CARD_1334) > 0 || CountActiveCardsOnField(1, CARD_1334) > 0
        || !CanActivateEffect(ref, NULL, 0))
        return 0;
    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *foe = ZONE(0, zone);

        if (foe->card.id && foe->isFaceUp && GetZoneCardAtk(0, zone) >= atk) {
            ChangeBattlePosition(1, ref->zone, 0, 0);
            z->positionLocked = 1;
            return 1;
        }
    }
    return 0;
}

int ExtraDeckAiActivateEffects(void)
{
    struct ChainEntry ref;
    int zone;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *z = ZONE(1, zone);
        u16 id = z->card.id;
        int number;

        if (!id || !z->isFaceUp)
            continue;
        number = NUMBER_OF(id);
        switch (number) {
        case CARD_MAGICIAN_OF_BLACK_CHAOS:
        case CARD_GAIA_THE_DRAGON_CHAMPION:
        case CARD_SUPER_WAR_LION:
            break;
        case CARD_THOUSAND_DRAGON:
        case CARD_THOUSAND_DRAGON_ALT:
            if (z->isDefense)       /* the coin only changes ATK */
                continue;
            break;
        case CARD_BICKURIBOX:
            break;
        default:
            continue;
        }
        ref.card = id;
        ref.player = 1;
        ref.zone = zone;
        ref.event = 0;
        ref.negated = 0;
        if (number == CARD_BICKURIBOX) {
            if (BickuriboxAiSwitch(&ref))
                return 1;
            continue;
        }
        if (!CanActivateEffect(&ref, NULL, 0))
            continue;
        if (number == CARD_GAIA_THE_DRAGON_CHAMPION || number == CARD_SUPER_WAR_LION) {
            int target = ChampionAiTarget(&ref);

            /* the human's only monster, in Attack Position: attacking it destroys it and deals damage too */
            if (target < 0 || (CountMonsters(0) < 2 && !ZONE(0, target)->isDefense))
                continue;
        }
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_POINT_AT_CARD, 1, zone << 8, 0);
        Chain_AddPending(0x80000000 | (CHAIN_KIND_MONSTER << 21) | ((u32)zone << 16) | id, 0);
        return 1;
    }
    return 0;
}
