#include "global.h"
#include "constants/game.h"         /* DUELIST_YUGI, DUELIST_BAKURA */
#include "main.h"                   /* gMain.opponent */
#include "save.h"                   /* gSaveData.duelRecords */
#include "second_decks.h"

/*
 * Second decks (universal-modder), in the three-Tribute effects build only.
 *
 * LoadOpponentDeck can build the CPU's deck from gOpponentAltDecks, a stronger second deck for each Tier 1
 * duelist, but its one caller, Campaign_SetupDuel, always passes 0. With this hook it passes 1 once the
 * player's record against that duelist (the wins the Statistics screen shows) reaches SECOND_DECK_WINS, so
 * the duel after the 10th win is the first against the second deck. Campaign_SetupDuel is the only place that loads a CPU
 * deck, so this covers every duel against these five.
 */

u16 OpponentUsesSecondDeck(void)
{
    u32 opponent = gMain.opponent;

    /* gOpponentAltDecks has entries for duelists 1-5 only */
    if (opponent < DUELIST_YUGI || opponent > DUELIST_BAKURA)
        return 0;
    return gSaveData.duelRecords[opponent].wins >= SECOND_DECK_WINS;
}
