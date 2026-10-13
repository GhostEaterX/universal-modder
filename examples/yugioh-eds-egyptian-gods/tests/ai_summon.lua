-- Oracle 3: does the CPU Tribute Summon a God?
-- From the duel_main1 state (player's turn 1), puts GOD in the CPU's hand (hand slot 0), two face-up
-- tribute fodder monsters in the CPU's monster zones 0 and 1, and a face-up Blue-Eyes White Dragon (3000 ATK)
-- on the player's side. The CPU only weighs Tribute Summons when its field can't attack well
-- (AiStepMainPhase: AiPlanAttack), so the dragon gives it a reason. The input script ends the player's turn;
-- during the CPU's turn this logs every change of the CPU's monster zones. The AI's move simulation writes
-- candidates into the zones and restores them within a few frames, so GOD only counts once it has stayed
-- on the field for HOLD frames.
local GOD = 817
pcall(function() GOD = tonumber(os.getenv("GOD")) or GOD end)
local P0 = 0x020192E4                -- gDuelPlayers[0]
local P1 = P0 + 0xD64                -- gDuelPlayers[1]
local THREAT = 82                    -- card ID 82, Blue-Eyes White Dragon
local ZONES, ZONE_SIZE, HAND = 0x28, 0x94, 0x684
local FODDER = 1                     -- card ID 1 (a Level 4 normal monster)
local HOLD = 60
local frame, last, since = 0, "", nil

local function zones()
    local t = {}
    for z = 0, 4 do t[#t + 1] = tostring(emu:read32(P1 + ZONES + z * ZONE_SIZE) & 0xFFF) end
    return table.concat(t, ",")
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        local a = P1 + HAND
        emu:write32(a, (emu:read32(a) & ~0xFFF) | GOD)
        for z = 0, 1 do
            local za = P1 + ZONES + z * ZONE_SIZE
            emu:write32(za, (emu:read32(za) & ~0x1FFF) | FODDER | 0x1000)    -- owner bit 12 = player 1
            emu:write8(za + 6, (emu:read8(za + 6) & ~0x3) | 0x2)              -- face up, attack position
        end
        local pa = P0 + ZONES
        emu:write32(pa, (emu:read32(pa) & ~0x1FFF) | THREAT)
        emu:write8(pa + 6, (emu:read8(pa + 6) & ~0x3) | 0x2)
        console:log(string.format("CPU hand[0] -> id %d (hand %d cards); CPU zones %s", GOD,
            emu:read8(P1 + 2), zones()))
    end
    local z = zones()
    if z ~= last then
        console:log(string.format("f%d CPU zones %s, CPU hand %d", frame, z, emu:read8(P1 + 2)))
        last = z
    end
    local present = false
    for v in z:gmatch("%d+") do
        if tonumber(v) == GOD then present = true end
    end
    if not present then
        since = nil
    elseif not since then
        since = frame
    elseif frame - since >= HOLD then
        console:log(string.format("GOD summoned by the CPU (on the field since frame %d)", since))
        EMU_STOP = 1
    end
end)
