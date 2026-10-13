-- Oracle 1: does the CPU's duel deck contain its God?
-- Forces the Campaign opponent (gMain.opponent) to OPP, taps into the duel, and once Campaign_SetupDuel has
-- loaded the CPU's deck (LoadOpponentDeck, which also runs RemoveOverLimitDeckCards) logs every card ID in
-- it. Run from the main_menu state with the duel_start inputs:
--   OPP=16 tools/emu.py lua npc_deck.lua --rom PATH --state main_menu --frames 1500 --keys "0 A; 30-1490/15 A"
local OPP = 16
pcall(function() OPP = tonumber(os.getenv("OPP")) or OPP end)
local OPP_ADDR = 0x030048B0          -- gMain+0x4870: bit 0 firstPlayer, bits 1-5 opponent, bits 6-7 result
local P1 = 0x020192E4 + 0xD64        -- gDuelPlayers[1] (0xD64 bytes per player)
local DECK, FUSION = 0x7C4, 0xA44     -- struct DuelCard deck[80], fusionDeck[80]; card ID = word & 0xFFF
local GODS = { [817] = "Obelisk", [818] = "Slifer", [819] = "Ra" }
local done = false

callbacks:add("frame", function()
    if done then return end
    local b = emu:read8(OPP_ADDR)
    local want = (b & 0xC1) | (OPP << 1)
    if b ~= want then emu:write8(OPP_ADDR, want) end
    local n, f = emu:read8(P1 + 3), emu:read8(P1 + 5)
    if n == 0 then return end
    local ids, gods = {}, {}
    for i = 0, n - 1 do
        local id = emu:read32(P1 + DECK + i * 4) & 0xFFF
        ids[#ids + 1] = tostring(id)
        if GODS[id] then gods[#gods + 1] = GODS[id] end
    end
    console:log(string.format("opponent %d: deck %d cards, fusion deck %d", OPP, n, f))
    console:log("deck ids: " .. table.concat(ids, " "))
    console:log("gods in deck: " .. (#gods > 0 and table.concat(gods, ", ") or "none"))
    done = true
    EMU_STOP = 1
end)
