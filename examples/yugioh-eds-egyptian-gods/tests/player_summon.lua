-- Oracle 2: can the player Tribute Summon a God?
-- From the duel_main1 state (player's turn 1, Main Phase 1), turns every hand card into GOD and puts two
-- face-up tribute fodder monsters in the player's monster zones 0 and 1. The input script then picks a
-- hand card and tries Summon. Every 30 frames it logs the card command menu's available-command mask
-- and what the player's monster zones hold; at the end it says whether GOD reached the field.
local GOD = 818
pcall(function() GOD = tonumber(os.getenv("GOD")) or GOD end)
local P0 = 0x020192E4                -- gDuelPlayers[0]
local ZONES, ZONE_SIZE, HAND = 0x28, 0x94, 0x684
local FODDER = 1                     -- card ID 1 (a Level 4 normal monster)
local NFODDER = 2                    -- how many fodder monsters (zones 0..NFODDER-1); env FODDER
pcall(function() NFODDER = tonumber(os.getenv("FODDER")) or NFODDER end)
local MENU = 0x02015EE8              -- gDuelCtrl.phase; the card menu state is logged via the zones
local frame, last = 0, ""

local function zones()
    local t = {}
    for z = 0, 4 do
        local a = P0 + ZONES + z * ZONE_SIZE
        t[#t + 1] = tostring(emu:read32(a) & 0xFFF)
    end
    return table.concat(t, ",")
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        local n = emu:read8(P0 + 2)
        for i = 0, n - 1 do
            local a = P0 + HAND + i * 4
            emu:write32(a, (emu:read32(a) & ~0xFFF) | GOD)
        end
        for z = 0, NFODDER - 1 do
            local a = P0 + ZONES + z * ZONE_SIZE
            emu:write32(a, (emu:read32(a) & ~0x1FFF) | FODDER)
            emu:write8(a + 6, (emu:read8(a + 6) & ~0x3) | 0x2)   -- face up, attack position
        end
        console:log(string.format("hand %d cards -> id %d; zones %s", n, GOD, zones()))
    end
    local z = zones()
    if z ~= last then
        console:log(string.format("f%d zones %s hand %d", frame, z, emu:read8(P0 + 2)))
        last = z
    end
end)
