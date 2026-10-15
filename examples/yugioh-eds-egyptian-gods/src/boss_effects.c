#include "global.h"
#include "card_data.h"              /* gCardIdToNumber, gCardStats, CARD_ID_MASK, CARD_STATS_TYPE */
#include "constants/card_stats.h"   /* CARD_TYPE_MAGIC */
#include "constants/cards.h"        /* CARD_* card numbers */
#include "constants/duel.h"         /* ZONE_*, CHAIN_KIND_MONSTER */
#include "constants/duel_cmds.h"    /* DUEL_CMD_*, DUEL_CMD_PLAYER */
#include "duel.h"                   /* gDuelPlayers, struct DuelZone */
#include "chain.h"                  /* struct ChainEntry, Chain_AddPending */
#include "duel_cmd.h"               /* DuelCmd_Push */
#include "duel_actions.h"           /* TributeMonster */
#include "summon.h"                 /* QueueSpecialSummonChoosePosition */
#include "effect.h"                 /* struct CardEffect, gCardEffectsMod, CanActivateEffect, TryAddEffectTarget */
#include "effect_handlers.h"        /* the original handlers these rows reuse */
#include "util.h"                   /* Random */
#include "god_effects.h"            /* GOD_EFFECT_ROWS */
#include "boss_effects.h"

/*
 * Boss effects (universal-modder), in the three-Tribute effects build only.
 *
 * A two-Tribute monster with 2400 or 2500 ATK and no effect is a poor boss next to the game's own Effect
 * monsters (Suijin, Jinzo, Barrel Dragon), so the CPU duelists' Normal-monster bosses get an effect that keeps
 * paying while they stay on the field. Each one reuses a mechanic the engine already has, so the CPU uses it:
 *
 *   Summoned Skull      piercing battle damage (CalcBattle's piercing rule)
 *   Millennium Golem    not destroyed by battle (CalcBattle's survive rule)
 *   Dark Magician       once per turn: destroy 1 Spell or Trap card your opponent controls (Barrel Dragon's
 *                       once-per-turn activation, Dust Tornado's pick, Mystical Space Typhoon's destroy)
 *   Red-Eyes B. Dragon  once per turn: toss a coin; heads destroys 1 monster your opponent controls (Barrel
 *                       Dragon's activation and pick, Time Wizard's coin)
 *   Red-Eyes Black Metal Dragon  attacking a monster, + a quarter of its ATK (Metalmorph's rule at half)
 *
 * The CPU also plays Joey's Metalmorph: a set Metalmorph goes onto its face-up Red-Eyes B. Dragon, and a Red-Eyes
 * with Metalmorph equipped is Tributed for Red-Eyes Black Metal Dragon from the deck, the upgrade the monster
 * menu offers the human. The original AI sets Metalmorph like any Trap and never activates it.
 *
 * None of them is protected from removal. The table rows only point at functions of this unit, which call the
 * original handlers: hookbuild relocates calls into the original code, and this keeps every handler pointer a
 * Thumb address of the new code, as check_effect_table.py requires.
 */

#define NUMBER_OF(id)       (gCardIdToNumber[(id) & CARD_ID_MASK])
#define CMD(player, cmd)    ((player) ? DUEL_CMD_PLAYER | (cmd) : (cmd))
#define ZONE(player, zone)  (&gDuelPlayers[(player) & 1].zones[(zone)])
#define COIN_HEADS          0

int BossFindCardEffect(u16 number)
{
    int i;

    for (i = GOD_EFFECT_ROWS; i < GOD_EFFECT_ROWS + BOSS_EFFECT_ROWS; i++) {
        if (gCardEffectsMod[i].number == number)
            return i;
    }
    return -1;
}

int BossPierces(u16 cardId)
{
    return NUMBER_OF(cardId) == CARD_SUMMONED_SKULL;
}

int BossBattleIndestructible(u16 cardId)
{
    return NUMBER_OF(cardId) == CARD_MILLENNIUM_GOLEM;
}

int BossAttackBonus(u16 cardId, int targetAtk)
{
    if (NUMBER_OF(cardId) != CARD_RED_EYES_BLACK_METAL_DRAGON || targetAtk <= 0)
        return 0;
    return (targetAtk + 3) / 4;     /* rounded up, as Metalmorph's half */
}

int BossOncePerTurnPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand)
{
    return EffectOncePerTurnPrepare(card, (int)chainLink, fromHand);
}

u16 BossOpponentSpellTrapCheck(struct ChainEntry *card, u16 pos)
{
    return EffectOpponentSpellTrapCheck(card, pos) != 0;
}

u16 BossOpponentMonsterCheck(struct ChainEntry *card, u16 pos)
{
    return EffectOpponentMonsterCheck(card, pos) != 0;
}

/* The CPU takes a face-down card first (the human's Trap Hole or Mirror Force), then a face-up one. The human
 * picks among the CPU's Spell and Trap cards, with Dust Tornado's prompt. */
int BossDarkMagicianChainB(struct ChainEntry *link, struct ChainEntry *prevLink)
{
    int pass;
    int zone;

    if (!link->player)
        return EffectDustTornadoChainB(link);
    link->numTargets = 0;
    for (pass = 0; pass <= 1; pass++) {
        for (zone = ZONE_SPELL_0; zone <= ZONE_FIELD; zone++) {
            struct DuelZone *z = ZONE(0, zone);

            if (z->card.id && z->isFaceUp == pass) {
                TryAddEffectTarget(link, 0, zone);
                return 1;
            }
        }
    }
    return 1;
}

/* Barrel Dragon's pick: the CPU takes the human's strongest monster; the human picks one of the CPU's. */
int BossRedEyesChainB(struct ChainEntry *link, struct ChainEntry *prevLink)
{
    return EffectOpponentMonsterChainB(link);
}

int BossDarkMagicianResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    if (!link->negated) {
        EffectDestroyTargetResolve(link);
        DuelCmd_Push(CMD(link->player, DUEL_CMD_SET_EFFECT_UNUSED), link->zone, 0, 0);
    }
    return EFFECT_STEP_DONE;
}

int BossRedEyesResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    if (!link->negated) {
        int tails = Random() & 1;
        int opponent = 1 - link->player;

        /* one coin, Heads called: the scene shows it land */
        DuelCmd_Push(CMD(link->player, DUEL_CMD_TOSS_COIN), COIN_HEADS, tails, 0);
        DuelCmd_Push(CMD(link->player, DUEL_CMD_OPEN_DUEL_SCREEN), 0, 0, 0);
        if (!tails && link->numTargets) {
            int zone = link->targets[0] >> 8;

            if (ZONE(opponent, zone)->card.id) {
                DestroyFieldCardByEffect(opponent, zone);
                OnCardDestroyedByEffect(link->player, opponent, zone);
            }
        }
        DuelCmd_Push(CMD(link->player, DUEL_CMD_SET_EFFECT_UNUSED), link->zone, 0, 0);
    }
    return EFFECT_STEP_DONE;
}

/* 1 if the CPU's deck holds Red-Eyes Black Metal Dragon. */
static int CpuDeckHasBlackMetalDragon(void)
{
    int i;

    for (i = 0; i < gDuelPlayers[1].deckCount; i++) {
        if (NUMBER_OF(gDuelPlayers[1].deck[i].id) == CARD_RED_EYES_BLACK_METAL_DRAGON)
            return 1;
    }
    return 0;
}

int BossMetalmorphTarget(struct ChainEntry *link)
{
    int zone;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *z = ZONE(link->player, zone);

        if (z->card.id && z->isFaceUp && NUMBER_OF(z->card.id) == CARD_RED_EYES_B_DRAGON
            && CountZoneLinksFromCard(link->player, zone, CARD_METALMORPH) == 0
            && EffectEquipTargetCheck(link, DUEL_LOC(link->player, zone)))
            return zone;
    }
    return -1;
}

/* The CPU's set Metalmorph, onto its face-up Red-Eyes when Red-Eyes Black Metal Dragon is in its deck: point at
 * it, flip it and add it to the chain, as AiTryPlaySpellTrap does with a set card. */
static int BossAiActivateMetalmorph(void)
{
    struct ChainEntry ref;
    int zone;

    if (!CpuDeckHasBlackMetalDragon())
        return 0;
    for (zone = ZONE_SPELL_0; zone <= ZONE_SPELL_4; zone++) {
        struct DuelZone *z = ZONE(1, zone);

        if (!z->card.id || z->isFaceUp || !z->canActivate || NUMBER_OF(z->card.id) != CARD_METALMORPH)
            continue;
        ref.card = z->card.id;
        ref.player = 1;
        ref.zone = zone;
        ref.event = 0;
        ref.negated = 0;
        if (BossMetalmorphTarget(&ref) < 0 || !CanActivateEffect(&ref, NULL, 0))
            continue;
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_POINT_AT_CARD, 1, zone << 8, 0);
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_FLIP_CARD, zone, 0, 0);
        Chain_AddPending(0x80000000 | (CHAIN_KIND_SPELL_TRAP << 21) | ((u32)zone << 16) | z->card.id, 0);
        return 1;
    }
    return 0;
}

/* The menu's upgrade, both of its steps at once (Tribute the Red-Eyes, then Special Summon Red-Eyes Black Metal
 * Dragon from the deck in a position the CPU picks). The summon is queued before the Tribute's command empties
 * the zone, so it needs another free zone. */
int BossAiUpgradeRedEyes(void)
{
    struct DuelCard taken;
    int zone;

    if (CountFreeMonsterZones(1) == 0 || !CpuDeckHasBlackMetalDragon()
        || CountActiveCardsOnField(0, CARD_1418) > 0 || CountActiveCardsOnField(1, CARD_1418) > 0)
        return 0;
    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *z = ZONE(1, zone);

        if (!z->card.id || !z->isFaceUp || NUMBER_OF(z->card.id) != CARD_RED_EYES_B_DRAGON
            || CountZoneLinksFromCard(1, zone, CARD_METALMORPH) == 0)
            continue;
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_POINT_AT_CARD, 1, zone << 8, 0);
        if (!TributeMonster(1, zone))
            return 0;
        if (TakeDeckCardByNumber(1, CARD_RED_EYES_BLACK_METAL_DRAGON, &taken))
            QueueSpecialSummonChoosePosition(1, &taken, 1, 1);
        return 1;
    }
    return 0;
}

int BossAiActivateEffects(void)
{
    struct ChainEntry ref;
    int zone;

    /* Red-Eyes: the upgrade, or the Metalmorph that leads to it, before its coin */
    if (BossAiUpgradeRedEyes())
        return 1;
    if (BossAiActivateMetalmorph())
        return BOSS_AI_METALMORPH;
    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *z = ZONE(1, zone);
        u16 id = z->card.id;
        int number;

        if (!id || !z->isFaceUp)
            continue;
        number = NUMBER_OF(id);
        if (number != CARD_DARK_MAGICIAN && number != CARD_DARK_MAGICIAN_ALT && number != CARD_RED_EYES_B_DRAGON)
            continue;
        ref.card = id;
        ref.player = 1;
        ref.zone = zone;
        ref.event = 0;
        ref.negated = 0;
        /* the check accepts a target only while the human has a Spell/Trap card (or a monster) */
        if (!CanActivateEffect(&ref, NULL, 0))
            continue;
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_POINT_AT_CARD, 1, zone << 8, 0);
        Chain_AddPending(0x80000000 | (CHAIN_KIND_MONSTER << 21) | ((u32)zone << 16) | id, 0);
        return 1;
    }
    return 0;
}
