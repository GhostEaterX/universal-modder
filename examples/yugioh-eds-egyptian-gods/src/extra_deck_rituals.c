#include "global.h"
#include "card_data.h"              /* gCardStats, gCardIdToNumber, CARD_ID_MASK, CARD_STATS_TYPE/KIND */
#include "card_list_view.h"         /* gCardListView */
#include "chain.h"                  /* struct ChainEntry, gChain.effectCard */
#include "constants/card_stats.h"   /* enum CardType, CardKind, CARD_TYPE_IS_MONSTER (patch_source.py) */
#include "constants/duel_cmds.h"    /* DUEL_CMD_REMOVE_CARD_FROM_FUSION_DECK, DUEL_CMD_PLAYER */
#include "duel.h"                   /* gDuelPlayers, CopyDuelCard */
#include "duel_cmd.h"               /* DuelCmd_Push */
#include "effect.h"                 /* struct RitualRecipe, FindRitualRecipe */
#include "save.h"                   /* gSaveData and the saved-deck helpers */
#include "extra_deck_rituals.h"

/*
 * Ritual monsters in the Extra Deck (universal-modder), in the three-Tribute effects build only.
 *
 * EDS's Extra Deck is the Fusion Deck: up to 20 cards beside the 40-60-card Deck, outside the Deck count, never
 * drawn. The original game puts a card there when its kind is Fusion, and it decides that in a dozen places:
 * Deck Edit filing a card, the CPU's deck lists loading, and a Fusion monster going back to the hand or the deck
 * in a duel (it returns to the Fusion Deck instead). Each of those now asks IsExtraDeckMonster, which also says
 * yes for a Ritual monster. The Ritual Magic cards then find their monster in the Fusion Deck (their Tributes
 * still come from the hand and the field, the level rule unchanged), and the CPU's spell logic, which asks the
 * same activation check, plays them with no change of its own.
 *
 * Two card effects follow: Cyber-Stein (Special Summon a Fusion monster from the Fusion Deck) keeps to Fusion
 * monsters, and Senju of the Thousand Hands, whose Ritual monster search would find nothing in the Deck now,
 * searches a Ritual Magic card like Sonic Bird (both are edits in patch_extra_deck_rituals.py). Gale Dogra still
 * sends any Fusion Deck card to the Graveyard; a Ritual monster sent there was never properly summoned, so
 * CanReviveGraveyardCard keeps it there, as it does a Fusion monster.
 */

#define STATS_OF(id)        (gCardStats[(id) & CARD_ID_MASK])
#define NUMBER_OF(id)       (gCardIdToNumber[(id) & CARD_ID_MASK])
#define CMD(player, cmd)    ((player) ? DUEL_CMD_PLAYER | (cmd) : (cmd))

/* 0x0819A990: per Ritual Magic card, its ritual monster and the level total (the table ends at spell 0). */
extern const struct RitualRecipe gRitualRecipes[];

u32 IsExtraDeckMonster(u16 cardId)
{
    u32 stats = STATS_OF(cardId);
    u32 type = CARD_STATS_TYPE(stats);
    u32 kind;

    /* a monster (patch_source.py's test, which counts the Gods) but not a God */
    if (!CARD_TYPE_IS_MONSTER(type) || type == CARD_TYPE_DIVINE)
        return 0;
    kind = CARD_STATS_KIND(stats);
    return kind == CARD_KIND_FUSION || kind == CARD_KIND_RITUAL;
}

static int FindFusionDeckRitualMonster(int player, int recipeIdx)
{
    struct DuelPlayer *p = &gDuelPlayers[player & 1];
    int i;

    if (recipeIdx < 0)
        return -1;
    for (i = 0; i < p->fusionCount; i++) {
        if (NUMBER_OF(p->fusionDeck[i].id) == gRitualRecipes[recipeIdx].monster)
            return i;
    }
    return -1;
}

int FusionDeckHasRitualMonster(int player, int recipeIdx)
{
    return FindFusionDeckRitualMonster(player, recipeIdx) >= 0;
}

int TakeRitualMonsterFromFusionDeck(struct ChainEntry *link)
{
    int i = FindFusionDeckRitualMonster(link->player, FindRitualRecipe(link->card));
    struct DuelCard *card;

    if (i < 0)
        return 0;
    card = &gDuelPlayers[link->player & 1].fusionDeck[i];
    CopyDuelCard(&gChain.effectCard, card);
    /* the card word as two halves, as Polymerization takes its Fusion monster */
    DuelCmd_Push(CMD(link->player, DUEL_CMD_REMOVE_CARD_FROM_FUSION_DECK), ((u16 *)card)[0], ((u16 *)card)[1], 0);
    return 1;
}

static u32 IsFusionKindMonster(u16 cardId)
{
    return IsExtraDeckMonster(cardId) && CARD_STATS_KIND(STATS_OF(cardId)) == CARD_KIND_FUSION;
}

u32 CountFusionDeckFusionMonsters(int player)
{
    struct DuelPlayer *p = &gDuelPlayers[player & 1];
    u32 n = 0;
    int i;

    for (i = 0; i < p->fusionCount; i++)
        n += IsFusionKindMonster(p->fusionDeck[i].id);
    return n;
}

void CollectFusionDeckFusionMonsters(int player)
{
    struct DuelPlayer *p = &gDuelPlayers[player & 1];
    int i;

    /* like the original's every-card copy, no source tags */
    for (i = 0; i < p->fusionCount; i++) {
        if (IsFusionKindMonster(p->fusionDeck[i].id))
            gCardListView.cards[gCardListView.count++] = *(u32 *)&p->fusionDeck[i];
    }
}

void MoveSavedRitualMonsters(void)
{
    struct SaveData *s = &gSaveData;
    int moved = 0;
    int i = 0;

    if (!IsSaveChecksumValid())
        return;
    while (i < s->deckSize) {
        u16 id = s->deck[i];

        if (!IsExtraDeckMonster(id) || s->trunk[id & CARD_ID_MASK].deckCopies == 0) {
            i++;
            continue;
        }
        /* takes the first copy out, which is deck[i], and closes the gap: deck[i] is the next card */
        RemoveCardFromSavedDeck(id);
        if (s->fusionDeckSize < FUSION_DECK_MAX_CARDS
            && (s32)s->trunk[id & CARD_ID_MASK].fusionCopies < GetCardCopyLimit(id))
            AddCardToSavedFusionDeck(id);
        else
            AddCardToTrunk(id);
        moved = 1;
    }
    if (moved)
        UpdateSaveChecksum();
}
