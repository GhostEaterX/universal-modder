#ifndef GUARD_GOD_EFFECTS_H
#define GUARD_GOD_EFFECTS_H

/*
 * Effects of the Egyptian God cards (universal-modder, examples/yugioh-eds-egyptian-gods).
 * patch_god_effects.py copies this header and src/god_effects.c into an eds-decomp tree; the edited
 * engine functions call the hooks below.
 */

#include "global.h"

struct ChainEntry;
struct ZoneCardStats;

#define GOD_NUMBER_OBELISK  1910    /* CARD_OBELISK_THE_TORMENTOR, id 817 */
#define GOD_NUMBER_SLIFER   1911    /* CARD_SLIFER_THE_SKY_DRAGON, id 818 */
#define GOD_NUMBER_RA       1912    /* CARD_THE_WINGED_DRAGON_OF_RA, id 819 */
#define GOD_ID_SLIFER       818
#define GOD_IS_GOD_NUMBER(n) ((u16)((n) - GOD_NUMBER_OBELISK) <= GOD_NUMBER_RA - GOD_NUMBER_OBELISK)

/* Zone-link kinds the engine does not have (enum ZoneLinkKind stops at 13). Every engine reader ignores
 * kinds it does not know, and only kinds 1, 2, 5, 7 and 10 are read as card locations. */
#define GOD_LINK_POINTS     14      /* links[i] = the LP Ra's controller paid: Ra's ATK and DEF */
#define GOD_LINK_PAD        15      /* links[i] = 0xFFFF; see GodAddLinkWithPad */

/* Rows of the relocated effect table gCardEffectsMod (data/god_effects_table.s): the 426 original rows, then
 * Obelisk and Ra. effect.h sends every reader of gCardEffects to it. */
#define GOD_EFFECT_ROWS     428

/* card_stats.c GetZoneCardStats, after the printed stats of a face-up monster: Slifer's and Ra's base. */
void GodApplyBaseStats(int player, int zone, struct ZoneCardStats *out);
/* summon_checks.c, the on-summon step of both Normal Summon executors: queue Ra's trigger. */
void GodOnNormalSummon(int player, int zone, u16 cardId);
/* summon_action.c SummonAction_Update, after any summon: Slifer's drain. Returns 1 if the summoned monster
 * was destroyed. */
int GodOnSummoned(int player, int zone, int summonKind);
/* summon_checks.c CanSummonFromHand, for the CPU: 0 for a Slifer that would be weak (fewer than 3 cards left
 * in the hand after it). */
int GodAiMaySummon(u16 cardId);
/* 1 if the opponent may not respond to this summon (a God's face-up Normal Summon). */
int GodSummonIsUnanswerable(u16 cardId, int summonKind, int isFaceUp);
/* card_list_viewer.c CanCardTargetZone: 1 if the face-up card can't be targeted (Obelisk). */
int GodIsUntargetable(u16 targetId);
/* ai_deck.c AiActivateMonsterEffects: the CPU's Obelisk and Ra. Returns 1 if it activated one. */
int GodAiActivateEffects(void);

/* Effect-table handlers (struct CardEffect slots). */
int GodObeliskPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand);
int GodObeliskChainB(struct ChainEntry *link, struct ChainEntry *prevLink);
int GodObeliskResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);
int GodRaPrepare(struct ChainEntry *card, struct ChainEntry *chainLink, u16 fromHand);
int GodRaChainB(struct ChainEntry *link, struct ChainEntry *prevLink);
int GodRaResolve(struct ChainEntry *link, struct ChainEntry *chainedTo);

#endif /* GUARD_GOD_EFFECTS_H */
