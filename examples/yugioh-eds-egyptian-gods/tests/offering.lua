-- Oracle: Ultimate Offering summons a God, with three Tributes in the 3-Tribute build.
-- From duel_main1: every hand card becomes GOD, FODDER face-up 7 Colored Fish go in monster zones 0.., and a
-- set Ultimate Offering (card ID 756) that may be activated goes in spell/trap zone 5. The keys activate it
-- and walk the summon. Logs the player's monster zones, hand size, LP and normalSummonUsed on every change:
-- a God on the field with normalSummonUsed still 0 means it came through Ultimate Offering.
local GOD = 818
local NFODDER = 3
pcall(function() GOD = tonumber(os.getenv("GOD")) or GOD end)
pcall(function() NFODDER = tonumber(os.getenv("FODDER")) or NFODDER end)
local P0 = 0x020192E4
local ZONES, ZONE_SIZE, HAND = 0x28, 0x94, 0x684
local OFFERING, FODDER = 756, 1
local frame, last = 0, ""

local function setcard(a, id, faceUp)
    emu:write32(a, (emu:read32(a) & ~0x1FFF) | id)
    emu:write8(a + 6, (emu:read8(a + 6) & ~0x3) | (faceUp and 0x2 or 0))
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        for i = 0, emu:read8(P0 + 2) - 1 do
            local a = P0 + HAND + i * 4
            emu:write32(a, (emu:read32(a) & ~0xFFF) | GOD)
        end
        for z = 0, NFODDER - 1 do setcard(P0 + ZONES + z * ZONE_SIZE, FODDER, true) end
        local st = P0 + ZONES + 5 * ZONE_SIZE
        setcard(st, OFFERING, false)
        emu:write8(st + 0x91, emu:read8(st + 0x91) | 0x4)      -- canActivate
    end
    local t = {}
    for z = 0, 5 do t[#t + 1] = tostring(emu:read32(P0 + ZONES + z * ZONE_SIZE) & 0xFFF) end
    local s = string.format("zones %s hand %d LP %d normalSummonUsed %d", table.concat(t, ","), emu:read8(P0 + 2),
        emu:read16(P0), (emu:read8(P0 + 8) >> 4) & 1)
    if s ~= last then
        console:log(string.format("f%d %s", frame, s))
        last = s
    end
end)
