-- fall-of-nouraajd c++ dark fantasy game
-- Copyright (C) 2026  Andrzej Lis
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- Reference Lua plugin: registers a JSON-constructible tile type whose onStep hook heals the
-- stepping creature, mirroring res/plugins/tile.py + the RoadTile entry in config/tiles.json.
-- Runs in the sandboxed environment built by CLuaHandler (see
-- docs/design/plugin_trust_boundary.md).

function load(context)
    context.registerType("LuaRoadTile", {
        base = "CTile",
        onStep = function(self, creature)
            creature:heal(1)
        end,
    })
    context.registerConfigJson("LuaRoadTile", [[{
        "class": "LuaRoadTile",
        "properties": {
            "animation": "images/tiles/road",
            "canStep": true,
            "label": "Lua Road",
            "tileType": "road",
            "description": "Heals 1 hp per step"
        }
    }]])
end
