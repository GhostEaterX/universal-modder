#ifndef GUARD_SECOND_DECKS_H
#define GUARD_SECOND_DECKS_H

/*
 * Second decks (universal-modder, examples/yugioh-eds-egyptian-gods), in the three-Tribute effects build: the
 * five Tier 1 duelists (Yugi, Tea, Joey, Tristan, Bakura) switch to their second deck, which the original game
 * never loads, once the player has beaten them SECOND_DECK_WINS times. patch_second_decks.py copies this header
 * and src/second_decks.c into an eds-decomp tree; the edited Campaign_SetupDuel calls the hook below.
 */

#include "global.h"

/* Wins against a Tier 1 duelist (gSaveData.duelRecords[duelist].wins) that switch them to their second deck. */
#define SECOND_DECK_WINS    10

/* campaign_steps.c Campaign_SetupDuel: LoadOpponentDeck's useAltDeck for gMain.opponent. */
u16 OpponentUsesSecondDeck(void);

#endif /* GUARD_SECOND_DECKS_H */
