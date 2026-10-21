# Copyright (C) 2026 Andrzej Lis
# SPDX-License-Identifier: GPL-3.0-or-later
"""Compile source-proven city scenes for one persistent actor per named NPC."""


def buildRelocations(source, *, usablePosition):
    facts = {row["sourceId"]: row for row in source.get("scriptedActors", [])}

    def scene(key, source_id, area, conditions, *, phase=5, time=None):
        fact = facts[source_id]
        if fact.get("areas") != [area] or not fact.get("position"):
            raise ValueError("Relocation requires one source area and a static position: " + source_id)
        x, y, z = usablePosition(area, fact["position"])
        result = {
            "id": key,
            "sourceArea": area,
            "x": x,
            "y": y,
            "z": z,
            "phaseMin": phase,
            "phaseMax": 7,
            "conditions": conditions,
            "sourceSpawnFact": source_id,
            "sourcePosition": fact["position"],
            "sourceConditions": fact.get("conditions", []),
        }
        if time:
            result["timeHours"] = time
        return result

    night = {"after": 21, "before": 4, "mode": "or"}
    first_active = {"questStages": {"narlenLookout": "active"}}
    second_active = {"questStages": {"narlenRogueStone": "active"}}
    stone = {"items": [{"item": "MISC45"}]}
    guild = scene(
        "guild",
        "AR0153.BCS#spawn6",
        "AR0153",
        {
            "any": [
                {"questStages": {"narlenLookout": "notStarted"}},
                {"kills": [{"creature": "WATCHM", "area": "AR0300"}]},
                {"all": [{"flags": ["narlenWarning"]}, {"not": second_active}]},
                {"all": [second_active, stone]},
                {"questStages": {"narlenRogueStone": "completed"}},
                {"questStages": {"narlenLookout": "failed"}},
                {"questStages": {"narlenRogueStone": "failed"}},
            ]
        },
    )
    guild["sourceSpawnAlternatives"] = ["AR0153.BCS#spawn7"]
    return [
        {
            "id": "narlen",
            "sourceCreature": "NARLEN",
            "canonicalActorId": "cityAr0153Actor3",
            "scenes": [
                scene(
                    "secondTest", "AR1300.BCS#spawn3", "AR1300", {"all": [second_active, {"not": stone}]}, time=night
                ),
                scene(
                    "lookout",
                    "AR0300.BCS#spawn3",
                    "AR0300",
                    {"all": [first_active, {"absentFlags": ["narlenWarning"]}]},
                    time=night,
                ),
                guild,
            ],
            "sourceGaps": [
                "Source guard arrival and warning deadline are separate from relocation.",
                "Native whole-hour TimeGT/TimeLT conversion is explicit; exact original timing remains pending.",
            ],
        },
        {
            "id": "aldeth",
            "sourceCreature": "ALDETH",
            "canonicalActorId": "cityAr1100ScriptActorAldeth",
            "scenes": [
                scene(
                    "league",
                    "AR0128.BCS#spawn0",
                    "AR0128",
                    {
                        "all": [
                            {"history": {"aldeth": "helped"}},
                            {"not": {"questStages": {"aldethLeague": "notStarted"}}},
                        ]
                    },
                ),
                scene("street", "AR1100.BCS#spawn9", "AR1100", {"history": {"aldeth": "helped"}}),
            ],
            "sourceGaps": [
                "Local accepted investigation replaces original AldethMove1->2 dialogue transition; original branch audit pending.",
                "DudleyFixes Chapter7 betrayal is excluded.",
            ],
        },
        {
            "id": "tamoko",
            "sourceCreature": "TAMOKO",
            "canonicalActorId": "cityAr0800ScriptActorTamoko",
            "scenes": [
                scene("undercity", "AR0123.BCS#spawn0", "AR0123", {"flags": ["tamokoMove2", "palaceCleared"]}, phase=7),
                scene(
                    "southwest",
                    "AR1100.BCS#spawn8",
                    "AR1100",
                    {"flags": ["tamokoMove1"], "absentFlags": ["tamokoMove2"]},
                    phase=7,
                ),
                scene("east", "AR0800.BCS#spawn7", "AR0800", {"absentFlags": ["tamokoMove1", "tamokoMove2"]}, phase=7),
            ],
            "sourceGaps": [
                "Each move flag requires its own authored source-supported conversation; moving alone never grants quest credit."
            ],
        },
    ]
