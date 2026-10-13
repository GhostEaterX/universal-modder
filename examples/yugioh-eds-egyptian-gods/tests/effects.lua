-- Oracle setup for the God effects. From the duel_main1 state (player's turn 1, Main Phase 1), stages the
-- field from environment variables, then logs the state on every change while the input script plays:
--   P_ZONES / C_ZONES  the player's / CPU's monster and spell-trap zones: "zone:id[:flags]" items, comma
--                      separated; flags: d = Defense Position, s = set (face down), a = may be activated
--                      (spell/trap canActivate). Zones 0-4 are monsters, 5-9 spells/traps.
--   P_HAND / C_HAND    card IDs for the first hand slots; P_HANDN / C_HANDN set the hand size.
--   P_LP / C_LP        Life Points.
-- Each log line: the monster zones (card IDs, "s" after a face-down one), LP, hand and graveyard sizes, and
-- the zone links of every monster that has any, as kind/count=value (Ra's paid LP is kind 14, Slifer's drain
-- kind 12 count 10, a pad kind 15), plus "noatk" while a monster has its cannot-attack flag.
local P = { [0] = 0x020192E4, [1] = 0x020192E4 + 0xD64 }   -- gDuelPlayers[0], [1]
local ZONES, ZONE_SIZE, HAND = 0x28, 0x94, 0x684
local frame, last = 0, ""

local function env(name)
    local v
    pcall(function() v = os.getenv(name) end)
    if v == "" then v = nil end
    return v
end

local function setzone(player, zone, id, flags)
    local a = P[player] + ZONES + zone * ZONE_SIZE
    emu:write32(a, (emu:read32(a) & ~0x1FFF) | id | (player == 1 and 0x1000 or 0))
    local f6 = emu:read8(a + 6) & ~0x3
    if not flags:find("s") then f6 = f6 | 0x2 end           -- face up
    if flags:find("d") or (zone <= 4 and flags:find("s")) then f6 = f6 | 0x1 end
    emu:write8(a + 6, f6)
    if flags:find("a") then emu:write8(a + 0x91, emu:read8(a + 0x91) | 0x4) end
end

local function stage(player, spec)
    if not spec then return end
    for item in spec:gmatch("[^,]+") do
        local zone, id, flags = item:match("^(%d+):(%d+):?(%a*)$")
        setzone(player, tonumber(zone), tonumber(id), flags or "")
    end
end

local function hand(player, spec, n)
    if spec then
        local i = 0
        for id in spec:gmatch("%d+") do
            local a = P[player] + HAND + i * 4
            emu:write32(a, (emu:read32(a) & ~0x1FFF) | tonumber(id) | (player == 1 and 0x1000 or 0))
            i = i + 1
        end
    end
    if n then emu:write8(P[player] + 2, tonumber(n)) end
end

local function side(player)
    local ids, links = {}, {}
    for z = 0, 4 do
        local a = P[player] + ZONES + z * ZONE_SIZE
        local id = emu:read32(a) & 0xFFF
        ids[#ids + 1] = tostring(id) .. ((id ~= 0 and (emu:read8(a + 6) & 0x2) == 0) and "s" or "")
        if id ~= 0 then
            local n, l = emu:read16(a + 0x8A), {}
            for i = 0, n - 1 do
                local kind = emu:read16(a + 0x4A + i * 2)
                l[#l + 1] = string.format("%d/%d=%d", kind & 0xFF, kind >> 8, emu:read16(a + 0x0A + i * 2))
            end
            local s = table.concat(l, " ")
            if (emu:read8(a + 0x8C) & 0x10) ~= 0 then s = s .. " noatk" end
            if s ~= "" then links[#links + 1] = string.format("%d[%s]", z, s) end
        end
    end
    return table.concat(ids, ","), table.concat(links, " ")
end

callbacks:add("frame", function()
    frame = frame + 1
    if frame == 1 then
        stage(0, env("P_ZONES"))
        stage(1, env("C_ZONES"))
        hand(0, env("P_HAND"), env("P_HANDN"))
        hand(1, env("C_HAND"), env("C_HANDN"))
        if env("P_LP") then emu:write16(P[0], tonumber(env("P_LP"))) end
        if env("C_LP") then emu:write16(P[1], tonumber(env("C_LP"))) end
    end
    local pz, pl = side(0)
    local cz, cl = side(1)
    local s = string.format("P %s C %s LP %d %d hand %d %d grave %d %d links P{%s} C{%s}", pz, cz,
        emu:read16(P[0]), emu:read16(P[1]), emu:read8(P[0] + 2), emu:read8(P[1] + 2),
        emu:read8(P[0] + 4), emu:read8(P[1] + 4), pl, cl)
    if s ~= last then
        console:log(string.format("f%d %s", frame, s))
        last = s
    end
end)
