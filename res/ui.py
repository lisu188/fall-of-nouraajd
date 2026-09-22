# fall-of-nouraajd c++ dark fantasy game
# Copyright (C) 2026  Andrzej Lis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Frontend choices and session flows; native engine imports stay at their call sites."""

from datetime import datetime
from contextlib import contextmanager
import json
from pathlib import Path
import re
from weakref import WeakKeyDictionary

import campaign

MAX_PREVIEW_BYTES = 16 * 1024 * 1024
SAVE_PREVIEW_CACHE = {}
SESSION_SAVE_STATUS = WeakKeyDictionary()
DEFAULT_RACE_ID = "templateDefault"
SCENARIO_TITLES = {
    "ninemarches": "Nine Marches",
    "sunderedmarch": "Sundered March",
    "usurpergate": "The Usurper's Gate",
    "vhulmarn": "Vhul'Marn",
    "multilevel": "Multilevel ruins",
    "test": "Training grounds",
}
DEFAULT_BINDINGS = {
    "north": "Up",
    "south": "Down",
    "east": "Right",
    "west": "Left",
    "wait": "Space",
    "save": "s",
    "inventory": "i",
    "journal": "j",
    "character": "c",
    "pause": "Escape",
    "console": "F12",
}
ACTION_LABELS = {
    "north": "Move north",
    "south": "Move south",
    "east": "Move east",
    "west": "Move west",
    "wait": "Wait one turn",
    "save": "Save game",
    "inventory": "Inventory",
    "journal": "Journal",
    "character": "Character",
    "pause": "Pause menu",
    "console": "Developer console",
}


def choose(game, title, choices, action_label="Select", back_label="Back"):
    """Return a validated enabled stable id; duplicate labels never identify choices."""
    rows = list(choices)
    ids = [row["id"] for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("Choice ids must be nonempty unique strings")
    handler = game.getGuiHandler()
    result = handler.showChoice(title, json.dumps(rows), action_label, back_label)
    return result if any(row["id"] == result and row.get("enabled", True) for row in rows) else ""


def confirm(game, title, body, confirm_label="Confirm", cancel_label="Cancel"):
    return game.getGuiHandler().showConfirm(title, body, confirm_label, cancel_label)


def notify(game, text):
    gui = game.getGui()
    if gui is not None:
        gui.notify(text)


def showError(game, text):
    game.getGuiHandler().showInfo(text, False)


def recordSessionSave(game, slot, operation):
    SESSION_SAVE_STATUS[game] = (
        f"Last successful {operation}: {datetime.now():%Y-%m-%d %H:%M:%S} · {displayName(slot)}."
    )


def sessionSaveStatus(game):
    return SESSION_SAVE_STATUS.get(game, "No successful save in this session.")


def discardProgressText(game):
    return "Progress since your last save or load will be lost.\n\n" + sessionSaveStatus(game)


@contextmanager
def loading(game, message):
    handler = game.getGuiHandler()
    try:
        handler.showLoading(message)
        yield
    finally:
        handler.hideLoading()


def displayName(value):
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value.replace("_", " ").replace("-", " "))
    return words[:1].upper() + words[1:]


def scenarioChoices(game, maps):
    rows = []
    provider = game.getResourcesProvider()
    for map_id in maps:
        label = SCENARIO_TITLES.get(map_id, displayName(map_id))
        detail = "Begin a standalone adventure in " + label + "."
        try:
            path = Path(provider.getPath(f"maps/{map_id}/config.json"))
            if path.is_file() and path.stat().st_size <= MAX_PREVIEW_BYTES:
                config = json.loads(path.read_text(encoding="utf-8"))
                for entry in config.values():
                    class_name = entry.get("class", "")
                    if class_name.endswith(("Start", "StartEvent")):
                        introduction = entry.get("properties", {}).get("text")
                        if isinstance(introduction, str) and introduction:
                            detail = introduction
                            break
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        row = {"id": map_id, "label": label, "detail": detail}
        artwork = campaign.artworkForMap(map_id)
        if artwork:
            row["image"] = artwork
        rows.append(row)
    return rows


def statSummary(stats, modifiers=False):
    if stats is None:
        return "Balanced; no attribute modifiers." if modifiers else ""
    parts = []
    for label, method in (
        ("Strength", "getStrength"),
        ("Agility", "getAgility"),
        ("Stamina", "getStamina"),
        ("Intelligence", "getIntelligence"),
    ):
        value = getattr(stats, method)()
        if not modifiers or value:
            parts.append(f"{label} {value:+d}" if modifiers else f"{label} {value}")
    return "\n".join(parts) or "Balanced; no attribute modifiers."


def characterChoices(game):
    classes = []
    races = []
    for class_id in sorted(game.getObjectHandler().getAllSubTypes("CPlayer")):
        template = game.createObject(class_id)
        label = template.getStringProperty("label") or class_id
        description = template.getStringProperty("description")
        stats = template.getStats()
        actions = [
            action.getStringProperty("label") or action.getTypeId() for action in template.getEffectiveInteractions()
        ]
        detail = "\n\n".join(part for part in (description, statSummary(stats)) if part)
        if actions:
            detail += "\n\nStarting abilities\n" + ", ".join(actions)
        classes.append({"id": class_id, "label": label, "detail": detail})
    for race_id in sorted(game.getObjectHandler().getAllSubTypes("CCreatureRace")):
        race = game.createObject(race_id)
        if not race.getBoolProperty("playerSelectable"):
            continue
        label = race.getStringProperty("label") or race_id
        description = race.getStringProperty("description")
        detail = "\n\n".join(part for part in (description, statSummary(race.getBaseStats(), True)) if part)
        races.append({"id": race_id, "label": label, "detail": detail})
    if not races:
        races.append({"id": DEFAULT_RACE_ID, "label": "Default race", "detail": "Keep the class's original race."})
    for row in classes:
        previews = {}
        for race in races:
            preview = game.createObject(row["id"])
            if race["id"] != DEFAULT_RACE_ID:
                preview.setObjectProperty("race", game.createObject(race["id"]))
            preview.heal(0)
            preview.addExp(0)
            detail = "\n\n".join(
                part for part in (preview.getStringProperty("description"), statSummary(preview.getStats())) if part
            )
            detail += f"\nHealth {preview.getHpMax()}\nMana {preview.getManaMax()}"
            actions = sorted(
                {
                    action.getStringProperty("label") or action.getTypeId()
                    for action in preview.getEffectiveInteractions()
                }
            )
            if actions:
                detail += "\n\nStarting abilities\n" + ", ".join(actions)
            equipment = [
                item.getStringProperty("label") or item.getTypeId()
                for slot, item in sorted(preview.getEquipped().items())
                if item is not None
            ]
            if equipment:
                detail += "\n\nStarting equipment\n" + ", ".join(equipment)
            previews[race["id"]] = detail
        row["previews"] = previews
    return classes, races


def chooseCharacter(game):
    classes, races = characterChoices(game)
    if not classes:
        showError(game, "No playable characters are available in this content set.")
        return "", ""
    class_id, race_id = game.getGuiHandler().showCharacterCreationOptions(json.dumps(classes), json.dumps(races))
    if class_id not in {row["id"] for row in classes} or race_id not in {row["id"] for row in races}:
        return "", ""
    return class_id, "" if race_id == DEFAULT_RACE_ID else race_id


def chooseCampaign(game):
    try:
        manifests = campaign.list_campaigns()
        chapter_counts = {manifest["campaignId"]: campaign.chapterCount(manifest) for manifest in manifests}
    except (OSError, ValueError):
        showError(game, "Campaign information could not be read. Check that the game content is installed.")
        return ""
    if not manifests:
        showError(game, "No campaigns are available.")
        return ""
    rows = []
    saves = savedGames(game)
    for manifest in manifests:
        first = manifest["scenarios"][manifest["start"]]
        latest = next((save for save in saves if save.get("campaignId") == manifest["campaignId"]), None)
        progress = "No saved progress."
        if latest:
            chapter = manifest["scenarios"].get(latest.get("scenarioId"), {}).get("title", "Saved adventure")
            progress = "Completed campaign" if latest.get("campaignFinished") else "Saved chapter: " + chapter
            progress += "\nResume from Load adventure: " + latest["label"]
        row = {
            "id": manifest["campaignId"],
            "label": manifest["title"],
            "detail": f"{manifest.get('description', '')}\n\nChapters: {chapter_counts[manifest['campaignId']]}"
            f"\n\n{progress}\n\nOpening chapter\n{first['title']}\n\n{first['briefing']}",
        }
        artwork = manifest.get("artwork") or first.get("artwork", "")
        if artwork:
            row["image"] = artwork
        rows.append(row)
    return choose(game, "Choose a campaign", rows, "Create character")


def newAdventure(game):
    from _game import CGameLoader

    while game.getContext().isActive():
        mode = choose(
            game,
            "New adventure",
            [
                {
                    "id": "campaign",
                    "label": "Campaign",
                    "detail": "Follow a story across linked chapters with your hero.",
                },
                {
                    "id": "scenario",
                    "label": "Standalone scenario",
                    "detail": "Choose an authored map and begin a self-contained adventure.",
                },
                {
                    "id": "random",
                    "label": "Random dungeon",
                    "detail": "Explore a newly generated dungeon with a fresh character.",
                },
            ],
            "Continue",
        )
        if not mode:
            return False
        destination = ""
        if mode == "campaign":
            destination = chooseCampaign(game)
        elif mode == "scenario":
            try:
                campaign_maps = {
                    scenario["map"]
                    for manifest in campaign.list_campaigns()
                    for scenario in manifest["scenarios"].values()
                }
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                showError(
                    game,
                    "Campaign information could not be read. Check the game content, then try again or go Back.",
                )
                continue
            maps = sorted(
                map_name for map_name in game.getResourcesProvider().getFiles("MAP") if map_name not in campaign_maps
            )
            if not maps:
                showError(game, "No scenarios are available.")
                continue
            destination = choose(
                game,
                "Choose a scenario",
                scenarioChoices(game, maps),
                "Create character",
            )
        if mode != "random" and not destination:
            continue
        class_id, race_id = chooseCharacter(game)
        if not class_id:
            continue
        if game.getMap() is not None and not confirm(
            game, "Start a new adventure?", discardProgressText(game), "Start adventure"
        ):
            continue
        try:
            loading_message = {
                "campaign": "Loading campaign...",
                "scenario": "Entering scenario...",
                "random": "Generating random dungeon...",
            }[mode]
            with loading(game, loading_message):
                if mode == "campaign":
                    campaign.start(game, destination, class_id, race_id)
                elif mode == "scenario":
                    CGameLoader.startGameWithPlayer(game, destination, class_id, race_id)
                else:
                    CGameLoader.startRandomGameWithPlayer(game, class_id, race_id)
                if game.getMap() is None or game.getMap().getPlayer() is None:
                    raise ValueError("No playable map loaded")
            SESSION_SAVE_STATUS.pop(game, None)
            return True
        except Exception:
            showError(game, "This adventure could not be started. Choose another scenario or check the game content.")
    return False


def readSavePreview(provider, slot):
    preview = {"id": slot, "label": displayName(slot), "detail": "Save slot: " + slot, "modified": 0}
    for suffix in (".json", ".json.bak"):
        try:
            resolved = provider.getPath("save/" + slot + suffix)
            if not resolved:
                continue
            path = Path(resolved)
            stat = path.stat()
            if not path.is_file():
                continue
            key = (str(path), stat.st_mtime_ns, stat.st_size)
            if key in SAVE_PREVIEW_CACHE:
                return dict(SAVE_PREVIEW_CACHE[key], id=slot, label=displayName(slot))
            preview["modified"] = stat.st_mtime
            preview["detail"] = f"Save slot: {slot}\nSaved: {datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M}"
            if stat.st_size <= MAX_PREVIEW_BYTES:
                document = json.loads(path.read_text(encoding="utf-8"))
                snapshot = document.get("snapshot", document)
                properties = snapshot.get("properties", {})
                map_name = document.get("mapName", properties.get("mapName", ""))
                if map_name:
                    preview["detail"] += "\nMap: " + displayName(map_name)
                if "turn" in properties:
                    preview["detail"] += "\nTurn: " + str(properties["turn"])
                player = next(
                    (
                        obj.get("properties", {})
                        for obj in properties.get("objects", [])
                        if isinstance(obj, dict)
                        and (obj.get("class") == "CPlayer" or obj.get("properties", {}).get("name") == "player")
                    ),
                    {},
                )
                for label, field in (("Class", "playerClassId"), ("Race", "raceId"), ("Level", "level")):
                    if player.get(field):
                        preview["detail"] += f"\n{label}: {displayName(str(player[field]))}"
                if player.get("campaign_id"):
                    preview["detail"] += "\nCampaign: " + displayName(player["campaign_id"])
                    preview["campaignId"] = player["campaign_id"]
                    preview["scenarioId"] = player.get("campaign_scenario", "")
                    preview["campaignFinished"] = bool(player.get("campaign_finished", False))
            if suffix.endswith(".bak"):
                preview["detail"] += "\n\nRecovery copy available; the game will attempt recovery on load."
            if len(SAVE_PREVIEW_CACHE) >= 128:
                SAVE_PREVIEW_CACHE.clear()
            SAVE_PREVIEW_CACHE[key] = dict(preview)
            return preview
        except (OSError, ValueError, TypeError, AttributeError, RecursionError):
            continue
    preview["detail"] += "\n\nPreview unavailable. The game will check the save and its recovery copy on load."
    return preview


def savedGames(game):
    provider = game.getResourcesProvider()
    return sorted(
        (readSavePreview(provider, slot) for slot in provider.getFiles("SAVE")),
        key=lambda row: (-row["modified"], row["id"]),
    )


def loadGame(game, slot, ask_replace=True):
    from _game import CGameLoader

    previous = game.getMap()
    if (
        previous is not None
        and ask_replace
        and not confirm(game, "Load saved adventure?", discardProgressText(game), "Load save")
    ):
        return False
    try:
        with loading(game, "Loading saved adventure..."):
            CGameLoader.loadSavedGame(game, slot)
            loaded = game.getMap()
            if loaded is None or loaded == previous:
                raise ValueError("Save loader retained the previous map")
    except Exception:
        showError(game, "The saved adventure could not be loaded. Choose another save or its recovery copy.")
        return False
    recordSessionSave(game, slot, "load")
    notify(game, "Loaded " + displayName(slot) + ".")
    return True


def loadMenu(game):
    while game.getContext().isActive():
        saves = savedGames(game)
        if not saves:
            showError(game, "No saved adventures are available yet.")
            return False
        slot = choose(game, "Load adventure", saves, "Load save")
        if not slot:
            return False
        if loadGame(game, slot):
            return True
    return False


def saveGame(game, slot):
    from _game import CMapLoader

    game_map = game.getMap()
    if game_map is None:
        return False
    try:
        with loading(game, "Saving your adventure..."):
            if not CMapLoader.saveWithResult(game_map, slot):
                raise OSError("Save write failed")
    except Exception:
        showError(
            game, "Your adventure could not be saved. Check that the save location is writable and has free space."
        )
        return False
    SAVE_PREVIEW_CACHE.clear()
    recordSessionSave(game, slot, "save")
    notify(game, "Saved " + displayName(slot) + ".")
    return True


def saveMenu(game):
    if game.getMap() is None:
        return False
    saves = savedGames(game)
    rows = [
        {"id": "newSave", "label": "New save", "detail": "Create a new save without replacing an existing adventure."}
    ]
    rows.extend(dict(row, id="slot:" + row["id"]) for row in saves)
    selection = choose(game, "Save adventure", rows, "Save")
    if not selection:
        return False
    if selection == "newSave":
        suggested = "journey-" + datetime.now().strftime("%Y%m%d-%H%M%S")
        while True:
            entered = game.getGuiHandler().showTextInput(
                "Name this save",
                "Use letters, numbers, spaces, hyphens, underscores, or single dots. "
                "Choose a name that helps you recognize this moment.",
                suggested,
            )
            if not entered:
                return False
            slot = normalizeSaveName(entered)
            if slot:
                break
            showError(
                game,
                "Use 1-80 letters, numbers, spaces, hyphens, underscores, or single dots. "
                "A save name cannot begin with a dot or contain two dots together.",
            )
            suggested = entered
    else:
        slot = selection.removeprefix("slot:")
    if slot in {row["id"] for row in saves}:
        if not confirm(
            game, "Replace this save?", "The selected save will be replaced by your current adventure.", "Replace save"
        ):
            return False
    return saveGame(game, slot)


def normalizeSaveName(value):
    value = re.sub(r"\s+", "-", value.strip())
    if 1 <= len(value) <= 80 and re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", value) and ".." not in value:
        return value
    return ""


def preferences(game):
    return json.loads(game.getGui().getUiPreferences())


def helpText(game):
    bindings = dict(DEFAULT_BINDINGS, **preferences(game).get("bindings", {}))
    controls = "\n".join(
        f"{ACTION_LABELS[action]}: {key}"
        for action, key in bindings.items()
        if action in ACTION_LABELS and action != "console"
    )
    return (
        "Exploring Nouraajd\n\nClick a walkable tile to preview a route. Choose Travel or press Enter to begin it. "
        "Use the movement keys for individual steps. Entering a location can open a conversation, encounter, or service. "
        "Press M to expand the map. Movement, waiting, and combat advance turns; inspecting menus does not.\n\n"
        + controls
        + "\n\nInventory and character\nSelect an item to inspect its details before using or equipping it. "
        "Choose Use or Equip explicitly; holding a key does not repeat those actions. "
        "Tab switches between regions, and / opens search. "
        "On compact management screens, [ and ] switch between panel regions.\n\n"
        "Combat\nSelect a living enemy, then select an action to inspect its effect, mana cost, and target. "
        "Some abilities affect your hero; check the preview before choosing Execute action. "
        "An action needing more mana than you have remains unavailable. "
        "Select an inventory item to inspect it, then choose Use item explicitly. "
        "Selecting targets, reading previews, and inspecting items do not take a turn. "
        "Choose Combat log or press L to review recent combat events without taking a turn. "
        "Escape opens the pause menu and keeps the encounter active.\n\n"
        "Menus\nUp/Down selects a row. Enter confirms. Escape returns to the previous screen. "
        "Use the mouse wheel or Page Up/Down to read longer descriptions. "
        "Character creation uses Tab to switch between class, race, and the compact preview.\n\n"
        "Save from the pause menu before leaving your adventure. Controls and readability settings "
        "can be changed in Settings."
    )


def showHelp(game):
    game.getGuiHandler().showCampaignScreen("Help", helpText(game), "Continue")


def configureBinding(game, settings):
    bindings = dict(DEFAULT_BINDINGS, **settings.get("bindings", {}))
    action = choose(
        game,
        "Controls",
        [
            {
                "id": action,
                "label": ACTION_LABELS[action] + ": " + key,
                "detail": "Choose a new key for " + ACTION_LABELS[action].lower() + ".",
            }
            for action, key in bindings.items()
            if action in ACTION_LABELS
        ],
        "Change key",
    )
    if not action:
        return None
    keys = ["Up", "Down", "Left", "Right", "Space", "Escape"]
    keys += list("abcdefghijklmnopqrstuvwxyz0123456789") + [f"F{number}" for number in range(1, 13)]
    used = {key.lower(): name for name, key in bindings.items() if name != action}
    reserved = {"m": "Reserved for the expanded map."}
    key = choose(
        game,
        ACTION_LABELS[action],
        [
            {
                "id": key,
                "label": key,
                "enabled": key.lower() not in used and key.lower() not in reserved,
                "detail": reserved.get(key.lower())
                or (
                    ("Already used for " + ACTION_LABELS.get(used[key.lower()], used[key.lower()]) + ".")
                    if key.lower() in used
                    else "Assign this key to " + ACTION_LABELS[action].lower() + "."
                ),
            }
            for key in keys
        ],
        "Assign key",
    )
    if not key:
        return None
    bindings[action] = key
    return dict(settings, bindings=bindings)


def showSettings(game):
    while game.getContext().isActive():
        settings = preferences(game)
        fields = [
            (
                "uiScale",
                "Interface scale",
                f"{settings.get('uiScale', 100)}%",
                "Resize the interface while keeping the game world readable.",
            ),
            (
                "textScale",
                "Text size",
                f"{settings.get('textScale', 100)}%",
                "Adjust menu, journal, and conversation text.",
            ),
            (
                "highContrast",
                "High contrast",
                "On" if settings.get("highContrast") else "Off",
                "Increase separation between controls and backgrounds.",
            ),
            (
                "reducedMotion",
                "Reduced motion",
                "On" if settings.get("reducedMotion") else "Off",
                "Reduce interface motion and decorative effects.",
            ),
            (
                "fullscreen",
                "Fullscreen",
                "On" if settings.get("fullscreen") else "Off",
                "Switch between windowed and fullscreen display.",
            ),
            (
                "tooltipDelayMs",
                "Tooltip delay",
                f"{settings.get('tooltipDelayMs', 500)} ms",
                "Choose how quickly hover information appears.",
            ),
            (
                "bindings",
                "Controls",
                "Customize",
                "Remap movement and menu shortcuts. Duplicate assignments are unavailable.",
            ),
        ]
        rows = [{"id": key, "label": f"{label}: {value}", "detail": detail} for key, label, value, detail in fields]
        rows.append(
            {
                "id": "reset",
                "label": "Reset defaults",
                "detail": "Restore the standard interface and controls.\n\nInterface scale: 100%\nText size: 100%"
                "\nHigh contrast: Off\nReduced motion: On\nFullscreen: Off\nTooltip delay: 300 ms"
                "\nMovement: arrow keys\nWait: Space\nInventory: I\nJournal: J\nCharacter: C\nSave: S\nPause: Escape",
            }
        )
        field = choose(
            game,
            "Settings",
            rows,
            "Change",
        )
        if not field:
            return
        if field == "reset":
            if not confirm(game, "Reset interface settings?", rows[-1]["detail"], "Reset defaults"):
                continue
            # The native preferences API fills omitted fields from its authoritative defaults.
            changed = {}
        elif field == "bindings":
            changed = configureBinding(game, settings)
            if changed is None:
                continue
        elif field in {"highContrast", "reducedMotion", "fullscreen"}:
            changed = dict(settings, **{field: not settings.get(field, False)})
        else:
            values = [0, 250, 500, 750, 1000, 1500] if field == "tooltipDelayMs" else [100, 125, 150, 175, 200]
            value = choose(
                game,
                next(label for key, label, _, _ in fields if key == field),
                [
                    {
                        "id": str(value),
                        "label": f"{value} ms" if field == "tooltipDelayMs" else f"{value}%",
                        "detail": (
                            f"Hover information will appear after {value} ms. The change applies immediately."
                            if field == "tooltipDelayMs"
                            else f"{'Interface' if field == 'uiScale' else 'Text'} size will be {value}%. "
                            "The change applies immediately and can be adjusted again here."
                        ),
                    }
                    for value in values
                ],
                "Apply",
            )
            if not value:
                continue
            changed = dict(settings, **{field: int(value)})
        if not game.getGui().applyUiPreferences(json.dumps(changed)):
            showError(game, "These settings could not be applied or saved. Your previous preferences remain available.")
        else:
            notify(game, "Settings saved.")


def mainMenu(game, in_session=False):
    while game.getContext().isActive():
        current = game.getMap() is not None
        saves = savedGames(game)
        continue_detail = (
            "Return to your current adventure.\n\n" + sessionSaveStatus(game)
            if current
            else (
                "Resume your most recent save.\n\n" + saves[0]["detail"]
                if saves
                else "Start an adventure or load a save first."
            )
        )
        action = choose(
            game,
            "Fall of Nouraajd",
            [
                {"id": "continue", "label": "Continue", "detail": continue_detail, "enabled": current or bool(saves)},
                {
                    "id": "new",
                    "label": "New adventure",
                    "detail": "Choose a campaign, standalone scenario, or random dungeon.",
                },
                {"id": "load", "label": "Load adventure", "detail": "Browse saved journeys and recovery information."},
                {"id": "settings", "label": "Settings", "detail": "Adjust display, text, accessibility, and controls."},
                {"id": "help", "label": "Help", "detail": "Learn how to explore, use menus, and save your progress."},
                {"id": "quit", "label": "Quit", "detail": "Leave the game."},
            ],
            "Open",
            "Resume" if current else "Quit",
        )
        if not game.getContext().isActive():
            return False
        if not action and current:
            return True
        if action == "continue":
            if current or (saves and loadGame(game, saves[0]["id"], ask_replace=False)):
                return True
        elif action == "new":
            if newAdventure(game):
                return True
        elif action == "load":
            if loadMenu(game):
                return True
        elif action == "settings":
            showSettings(game)
        elif action == "help":
            showHelp(game)
        elif action in {"quit", ""}:
            if not current or confirm(game, "Quit the game?", discardProgressText(game), "Quit game"):
                game.getContext().shutdown()
                return False
    return False


def pause(game):
    while game.getContext().isActive() and game.getMap() is not None:
        saves = savedGames(game)
        action = choose(
            game,
            "Paused",
            [
                {
                    "id": "resume",
                    "label": "Resume",
                    "detail": "Return to your adventure.\n\n" + sessionSaveStatus(game),
                },
                {
                    "id": "save",
                    "label": "Save",
                    "detail": "Create a new save or replace a previous one.\n\n" + sessionSaveStatus(game),
                },
                {
                    "id": "load",
                    "label": "Load",
                    "detail": "Browse saved adventures." if saves else "No saved adventures are available yet.",
                    "enabled": bool(saves),
                },
                {"id": "settings", "label": "Settings", "detail": "Change display and controls."},
                {"id": "help", "label": "Help", "detail": "Read the controls and exploration guide."},
                {"id": "menu", "label": "Main menu", "detail": "Choose another adventure or continue this one."},
                {"id": "quit", "label": "Quit", "detail": "Leave the game.\n\n" + sessionSaveStatus(game)},
            ],
            "Open",
            "Resume",
        )
        if action in {"", "resume"}:
            return
        if action == "save":
            saveMenu(game)
        elif action == "load":
            if loadMenu(game):
                return
        elif action == "settings":
            showSettings(game)
        elif action == "help":
            showHelp(game)
        elif action == "menu":
            mainMenu(game, in_session=True)
            return
        elif action == "quit" and confirm(game, "Quit the game?", discardProgressText(game), "Quit game"):
            game.getContext().shutdown()
            return


def showDefeat(game):
    game_map = game.getMap()
    if game_map is None or game_map.getPlayer() is None:
        return
    player = game_map.getPlayer()
    raw = player.getStringProperty("uiDefeatReceipt")
    if not raw:
        return
    try:
        receipt = json.loads(raw)
    except (TypeError, ValueError):
        return
    if not isinstance(receipt, dict):
        return
    player.setStringProperty("uiDefeatReceipt", "")
    lost = receipt.get("lostItems", [])
    items = "\n".join(
        f"{item.get('label') or item.get('id', 'Item')} x{item.get('count', 1)}"
        for item in lost
        if isinstance(item, dict)
    )
    detail = "You recovered in " + displayName(str(receipt.get("map", game_map.getMapName()))) + "."
    if "hp" in receipt:
        detail += "\nHealth after recovery: " + str(receipt["hp"])
    detail += "\n\nItems lost\n" + (items or "No inventory items were lost.")
    while game.getContext().isActive():
        action = choose(
            game,
            "Defeated",
            [
                {"id": "continue", "label": "Continue adventure", "detail": detail},
                {"id": "load", "label": "Load saved adventure", "detail": detail + "\n\nReturn to a previous save."},
            ],
            "Continue",
            "Return to adventure",
        )
        if action != "load" or loadMenu(game):
            return
