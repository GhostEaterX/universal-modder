#include "global.h"
#include "card_data.h"              /* gCardIdToNumber, CARD_ID_MASK */
#include "constants/cards.h"
#include "constants/duel.h"         /* ZONE_*, RESPONSE_*, SUMMON_ACTION_*, CHAIN_KIND_MONSTER, PICK_* */
#include "constants/duel_cmds.h"    /* DUEL_CMD_* */
#include "constants/sound.h"        /* SE_ERROR */
#include "duel.h"                   /* gDuelPlayers, struct ZoneCardStats, Count* queries */
#include "chain.h"                  /* struct ChainEntry, gChain, Chain_AddPending */
#include "duel_cmd.h"               /* DuelCmd_Push */
#include "duel_actions.h"           /* TributeMonster, QueueAddZoneLink */
#include "duel_screen.h"            /* gDuelScreen, DuelCursor_PickTarget */
#include "effect.h"                 /* enum EffectStep, CanActivateEffect, target helpers */
#include "effect_handlers.h"        /* EffectTargetableMonsterChainB, EffectDestroyTargetResolve */
#include "text_box.h"               /* gTextBox, TextBoxOpen, TextBoxSetMenu */
#include "sound.h"                  /* PlaySE */
#include "gba.h"                    /* B_BUTTON */
#include "main.h"                   /* gMain.newKeys */
#include "ai.h"                     /* AiFindStrongestMonster */
#include "god_effects.h"

/*
 * The Egyptian God cards' effects (universal-modder). This unit exists only in the mod tree: hookbuild.py
 * links it into the relocated code, and the edited engine functions call into it.
 *
 *   Obelisk  Tribute 2 other monsters: destroy all monsters the opponent controls; Obelisk can't attack this
 *            turn. Neither player can target it with card effects.
 *   Slifer   ATK and DEF = 1000 x the cards in its controller's hand. When the opponent Normal or Special
 *            Summons a monster in Attack Position, it loses 2000 ATK; if that reduces its ATK to 0, it is
 *            destroyed.
 *   Ra       When Normal Summoned: you may pay LP until you have 100; its ATK and DEF become the amount
 *            paid. Pay 1000 LP, target 1 monster on the field: destroy it.
 *   All      A God's Normal Summon can't be answered, and a God can't be Normal Set (the edits in the
 *            summon code and the card menu).
 *
 * Ra's paid amount and Slifer's 2000 ATK loss are zone links, so they go when the card leaves its zone.
 */

#define GZ(player, zone)    (&gDuelPlayers[(player) & 1].zones[(zone)])
#define GZ_ID(z)            ((z)->card.id)
#define NUMBER_OF(id)       (gCardIdToNumber[(id) & CARD_ID_MASK])
#define CMD(player, cmd)    ((player) ? DUEL_CMD_PLAYER | (cmd) : (cmd))
#define LOC(player, zone)   ((u8)(player) | (u16)((u8)(zone) << 8))

#define GOD_TEXT_POS        TEXTBOX_POS(5, 2)       /* the resolve prompts' box (effect_resolve1.c) */
#define GOD_TEXT_SIZE       TEXTBOX_SIZE(20, 9)
#define RA_KEEP_LP          100
#define RA_DESTROY_COST     1000
#define SLIFER_DRAIN        2000
#define SLIFER_DRAIN_LINK   ZONE_LINK_KIND(ZONE_LINK_ATK_DOWN_200, SLIFER_DRAIN / 200)
#define SLIFER_AI_MIN_HAND  4       /* the CPU summons Slifer only when 3+ cards stay in its hand (3000+ ATK) */

const u8 gStrGodSelectFirstTribute[] = "Please select 1st monster as @3Tribute@0.";
const u8 gStrGodSelectSecondTribute[] = "Please select 2nd monster as @3Tribute@0.";
const u8 gStrGodRaPayPrompt[] = "Do you wish to pay @3LP@0 until you have @3100LP@0 left?";

/*
 * Add a link, then a pad link right after it. RemoveLinksToZone (duel_zones.c) skips the link that follows any
 * link it does not read as a card location (an engine quirk), so without the pad an Equip put on the monster
 * later could keep its link after the Equip is gone.
 */
static void GodAddLinkWithPad(int player, u16 target, u16 at, u16 kind)
{
    QueueAddZoneLink(player, target, at, kind);
    QueueAddZoneLink(player, 0xFFFF, at, GOD_LINK_PAD);
}

/* ---- Stats ------------------------------------------------------------------------------------------- */

void GodApplyBaseStats(int player, int zone, struct ZoneCardStats *out)
{
    struct DuelZone *z;
    int i;

    switch (NUMBER_OF(out->id)) {
    case GOD_NUMBER_SLIFER:
        out->atk = gDuelPlayers[player & 1].handCount * 1000;
        out->def = out->atk;
        break;
    case GOD_NUMBER_RA:
        z = GZ(player, zone);
        for (i = 0; i < z->numLinks; i++) {
            if ((u8)z->linkKinds[i] == GOD_LINK_POINTS) {
                out->atk = z->links[i];
                out->def = z->links[i];
                break;
            }
        }
        break;
    }
}

/* ---- Summons ----------------------------------------------------------------------------------------- */

void GodOnNormalSummon(int player, int zone, u16 cardId)
{
    if (NUMBER_OF(cardId) != GOD_NUMBER_RA || gDuelPlayers[player & 1].lifePoints <= RA_KEEP_LP)
        return;
    Chain_AddPending(((u32)(player & 1) << 31) | (RESPONSE_SUMMONED << 25) | (CHAIN_KIND_MONSTER << 21)
                     | ((u32)zone << 16) | cardId,
                     LOC(player, zone));
}

int GodOnSummoned(int player, int zone, int summonKind)
{
    int opponent = 1 - (player & 1);
    struct DuelZone *z = GZ(player, zone);
    int atk;

    if (summonKind == SUMMON_ACTION_FLIP)
        return 0;
    if (!GZ_ID(z) || !z->isFaceUp || z->isDefense)
        return 0;
    if (CountFaceUpMonstersByNumber(opponent, GOD_NUMBER_SLIFER) <= 0)
        return 0;
    atk = (int)GetZoneCardAtk(player & 1, zone);
    if (atk <= 0)
        return 0;
    DuelCmd_Push(CMD(opponent, DUEL_CMD_SHOW_CARD_EFFECT), GOD_ID_SLIFER, 1, 0);
    if (atk <= SLIFER_DRAIN) {
        DestroyFieldCardByEffect(player & 1, zone);
        OnCardDestroyedByEffect(opponent, player & 1, zone);
        return 1;
    }
    GodAddLinkWithPad(opponent, GOD_ID_SLIFER, LOC(player, zone), SLIFER_DRAIN_LINK);
    return 0;
}

int GodSummonIsUnanswerable(u16 cardId, int summonKind, int isFaceUp)
{
    if (!isFaceUp || !GOD_IS_GOD_NUMBER(NUMBER_OF(cardId)))
        return 0;
    return summonKind == SUMMON_ACTION_NORMAL || summonKind == SUMMON_ACTION_NORMAL_CHOOSE_POSITION;
}

int GodIsUntargetable(u16 targetId)
{
    return NUMBER_OF(targetId) == GOD_NUMBER_OBELISK;
}

int GodAiMaySummon(u16 cardId)
{
    return NUMBER_OF(cardId) != GOD_NUMBER_SLIFER || gDuelPlayers[1].handCount >= SLIFER_AI_MIN_HAND;
}

/* ---- Obelisk ----------------------------------------------------------------------------------------- */

static int CountOpponentMonsters(int player)
{
    int zone, count = 0;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++)
        if (GZ_ID(GZ(1 - player, zone)))
            count++;
    return count;
}

int GodObeliskPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand)
{
    if (fromHand || chainLink)
        return 0;
    if (CountTributableMonsters(card->player, card->zone) < 2)
        return 0;
    return CountOpponentMonsters(card->player) > 0;
}

/* The CPU's cheapest monster to Tribute other than the zones a and b (tokens first, never a God), or -1. */
static int GodAiPickTribute(int a, int b)
{
    struct ZoneCardStats stats;
    int zone, best = -1, bestValue = 0x7FFFFFFF;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        u16 id = GZ_ID(GZ(1, zone));
        int value;

        if (!id || zone == a || zone == b || !IsTributableMonster(1, zone) || GOD_IS_GOD_NUMBER(NUMBER_OF(id)))
            continue;
        GetZoneCardStats(1, zone, &stats);
        value = stats.atk + stats.def;
        if (NUMBER_OF(id) >= 1920 && NUMBER_OF(id) < 2000)  /* tokens */
            value = -1;
        if (value < bestValue) {
            best = zone;
            bestValue = value;
        }
    }
    return best;
}

/* Tribute the two picked monsters: the cost, paid when the effect is activated. */
static void GodPayObeliskTributes(struct ChainEntry *link)
{
    int i;

    for (i = 0; i < link->numTargets; i++)
        TributeMonster(link->player, link->targets[i] >> 8);
    link->numTargets = 0;
}

int GodObeliskChainB(struct ChainEntry *link, struct ChainEntry *prevLink)
{
    if (link->player) {
        int t1 = GodAiPickTribute(link->zone, -1);
        int t2 = t1 < 0 ? -1 : GodAiPickTribute(link->zone, t1);

        link->numTargets = 0;
        if (t2 >= 0) {
            AddEffectTargetUnchecked(link, 1, t1);
            AddEffectTargetUnchecked(link, 1, t2);
            GodPayObeliskTributes(link);
        }
        return 1;
    }
    /* Steps: 0 and 2 open the 1st / 2nd prompt, 1 and 3 wait for the pick; B starts over. A prompt opens on
     * the frame after a pick, or the A press of the pick would close it at once. */
    switch (gChain.targetStep) {
    case 0:
        link->numTargets = 0;
        /* fall through */
    case 2:
        TextBoxOpen(TARGET_PROMPT_POS, TARGET_PROMPT_SIZE, TEXTBOX_FLAGS_DEFAULT,
                    gChain.targetStep ? gStrGodSelectSecondTribute : gStrGodSelectFirstTribute);
        gChain.targetStep++;
        return 0;
    }
    if (gMain.newKeys & B_BUTTON) {
        gChain.targetStep = 0;
        return 0;
    }
    if (DuelCursor_PickTarget(PICK_ANY_MONSTER)) {
        int zone = gDuelScreen.selArea + gDuelScreen.selIndex;

        if (gDuelScreen.selPlayer == 0 && zone <= ZONE_MONSTER_4 && zone != link->zone
            && IsTributableMonster(0, zone)
            && (link->numTargets == 0 || (link->targets[0] >> 8) != zone)) {
            AddEffectTargetUnchecked(link, 0, zone);
            if (link->numTargets >= 2) {
                GodPayObeliskTributes(link);
                return 1;
            }
            gChain.targetStep = 2;
            return 0;
        }
        PlaySE(SE_ERROR);
    }
    return 0;
}

/* START: Obelisk can't attack this turn; then one opponent's monster per call, as Raigeki does. */
int GodObeliskResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    int foe = 1 - link->player;
    int zone;

    if (link->negated)
        return EFFECT_STEP_DONE;
    if (gChain.effectStep == EFFECT_STEP_START) {
        struct DuelZone *self = GZ(link->player, link->zone);

        if (GZ_ID(self) && NUMBER_OF(GZ_ID(self)) == GOD_NUMBER_OBELISK)
            DuelCmd_Push(CMD(link->player, DUEL_CMD_SET_CANNOT_ATTACK), link->zone, 1, 0);
    }
    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        if (IsZoneTargetable(foe, zone)) {
            DestroyFieldCardByEffect(foe, zone);
            OnCardDestroyedByEffect(link->player, foe, zone);
            return EFFECT_STEP_2;
        }
    }
    return EFFECT_STEP_DONE;
}

/* ---- Ra ---------------------------------------------------------------------------------------------- */

int GodRaPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand)
{
    int player, zone;

    if (fromHand || chainLink)
        return 0;
    if (card->event == RESPONSE_SUMMONED)
        return gDuelPlayers[card->player].lifePoints > RA_KEEP_LP;
    if (gDuelPlayers[card->player].lifePoints <= RA_DESTROY_COST)
        return 0;
    for (player = 0; player <= 1; player++)
        for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++)
            if (CanCardTargetZone(card->card, player, zone))
                return 1;
    return 0;
}

/* The summon trigger takes no target; the destroy effect picks one, then pays its 1000 LP. */
int GodRaChainB(struct ChainEntry *link, struct ChainEntry *prevLink)
{
    int done;

    if (link->event == RESPONSE_SUMMONED)
        return 1;
    done = EffectTargetableMonsterChainB(link, (int)prevLink);
    if (done && link->numTargets == 1)
        DuelCmd_Push(CMD(link->player, DUEL_CMD_LOSE_LP), RA_DESTROY_COST, 1, 0);
    return done;
}

static void GodRaPay(struct ChainEntry *link, u16 paid)
{
    DuelCmd_Push(CMD(link->player, DUEL_CMD_LOSE_LP), paid, 1, 0);
    GodAddLinkWithPad(link->player, paid, LOC(link->player, link->zone), GOD_LINK_POINTS);
}

/* The summon trigger: the CPU pays when Ra ends up stronger than 4000; the human gets a Yes/No prompt. */
int GodRaResolve(struct ChainEntry *link, struct ChainEntry *chainedTo)
{
    struct DuelZone *self;
    u16 lp;

    if (link->event != RESPONSE_SUMMONED)
        return EffectDestroyTargetResolve(link);
    if (link->negated)
        return EFFECT_STEP_DONE;
    self = GZ(link->player, link->zone);
    lp = gDuelPlayers[link->player].lifePoints;
    if (!GZ_ID(self) || !self->isFaceUp || NUMBER_OF(GZ_ID(self)) != GOD_NUMBER_RA || lp <= RA_KEEP_LP)
        return EFFECT_STEP_DONE;
    if (link->player) {
        if (lp - RA_KEEP_LP > 4000)
            GodRaPay(link, lp - RA_KEEP_LP);
        return EFFECT_STEP_DONE;
    }
    switch (gChain.effectStep) {
    case EFFECT_STEP_START:
        TextBoxOpen(GOD_TEXT_POS, GOD_TEXT_SIZE, TEXTBOX_FLAGS_DEFAULT, gStrGodRaPayPrompt);
        TextBoxSetMenu(TEXTBOX_MENU_YES_NO, NULL, NULL);
        return EFFECT_STEP_2;
    case EFFECT_STEP_2:
        if (gTextBox.result)
            GodRaPay(link, lp - RA_KEEP_LP);
        return EFFECT_STEP_3;
    }
    return EFFECT_STEP_DONE;
}

/* ---- CPU --------------------------------------------------------------------------------------------- */

/* Obelisk: it clears more ATK than it Tributes, and the player has 2+ monsters or one Obelisk can't beat. */
static int GodAiWantsObelisk(int zone)
{
    int t1 = GodAiPickTribute(zone, -1);
    int t2 = t1 < 0 ? -1 : GodAiPickTribute(zone, t1);
    int i, foes = 0, foeSum = 0, foeBest = 0;

    if (t2 < 0)
        return 0;
    for (i = ZONE_MONSTER_0; i <= ZONE_MONSTER_4; i++) {
        if (GZ_ID(GZ(0, i))) {
            int atk = (int)GetZoneCardAtk(0, i);

            foes++;
            foeSum += atk;
            if (atk > foeBest)
                foeBest = atk;
        }
    }
    if (foes < 2 && foeBest < (int)GetZoneCardAtk(1, zone))
        return 0;
    return foeSum > (int)GetZoneCardAtk(1, t1) + (int)GetZoneCardAtk(1, t2);
}

/* Ra: the player's strongest monster (the one the CPU's target pick takes) has 2000+ ATK and can be
 * targeted, and the CPU keeps more than 2000 LP after paying. */
static int GodAiWantsRaDestroy(u16 raId)
{
    int target = AiFindStrongestMonster(0, -1, 1, 1);

    if (gDuelPlayers[1].lifePoints <= RA_DESTROY_COST + 2000 || target < 0)
        return 0;
    return CanCardTargetZone(raId, 0, target) && (int)GetZoneCardAtk(0, target) >= 2000;
}

int GodAiActivateEffects(void)
{
    struct ChainEntry ref;
    int zone;

    for (zone = ZONE_MONSTER_0; zone <= ZONE_MONSTER_4; zone++) {
        struct DuelZone *z = GZ(1, zone);
        u16 id = GZ_ID(z);
        int number;

        if (!id || !z->isFaceUp)
            continue;
        number = NUMBER_OF(id);
        if (number != GOD_NUMBER_OBELISK && number != GOD_NUMBER_RA)
            continue;
        ref.card = id;
        ref.player = 1;
        ref.zone = zone;
        ref.event = 0;
        ref.negated = 0;
        if (!CanActivateEffect(&ref, NULL, 0))
            continue;
        if (number == GOD_NUMBER_OBELISK ? !GodAiWantsObelisk(zone) : !GodAiWantsRaDestroy(id))
            continue;
        DuelCmd_Push(DUEL_CMD_PLAYER | DUEL_CMD_POINT_AT_CARD, 1, zone << 8, 0);
        Chain_AddPending(0x80000000 | (CHAIN_KIND_MONSTER << 21) | ((u32)zone << 16) | id, 0);
        return 1;
    }
    return 0;
}
