from _game import *
import json

import campaign
from quest_state import LegacyBoolFlag
from quest_state import PlayerQuestRegistry
from quest_state import QuestStateStore
from quest_state import ensure_quest
from quest_state import player_has_quest
from quest_state import quest_id

set_logger_sink("disabled", None)

_native_configure_playtest_trace = configure_playtest_trace
_native_get_playtest_trace_records = get_playtest_trace_records
_native_drain_playtest_trace_records = drain_playtest_trace_records
_native_record_playtest_trace_json = record_playtest_trace_json


def configure_playtest_trace(enabled=True, output_path=None, max_records=1000):
    _native_configure_playtest_trace(bool(enabled), output_path, max_records)


def _parse_playtest_trace(records):
    return [json.loads(record) for record in records]


def get_playtest_trace():
    return _parse_playtest_trace(_native_get_playtest_trace_records())


def drain_playtest_trace():
    return _parse_playtest_trace(_native_drain_playtest_trace_records())


def record_playtest_trace(event, **fields):
    if playtest_trace_enabled():
        _native_record_playtest_trace_json(event, json.dumps(fields, sort_keys=True))


def claim_once(owner, property_name):
    if owner.getBoolProperty(property_name):
        return False
    owner.setBoolProperty(property_name, True)
    return True


def remove_runtime_actors(game_map, names=(), prefixes=()):
    """Idempotently remove runtime actor objects from a map.

    Objects are matched by exact name (``names``) or by an explicitly reviewed
    name prefix (``prefixes``). Objects whose names merely overlap a target name
    are preserved unless a prefix that matches them was explicitly passed, so a
    similar but non-matching actor is never collateral. The helper tolerates
    actors that are already gone and returns the number of objects removed.
    """
    name_set = frozenset(name for name in names if name)
    prefix_tuple = tuple(prefix for prefix in prefixes if prefix)
    if not name_set and not prefix_tuple:
        return 0

    def _matches(obj):
        name = obj.getName()
        if not name:
            return False
        if name in name_set:
            return True
        return bool(prefix_tuple) and name.startswith(prefix_tuple)

    doomed = []
    game_map.forObjects(doomed.append, _matches)
    for obj in doomed:
        game_map.removeObject(obj)
    return len(doomed)


def playtest_object_ref(obj):
    if obj is None:
        return None
    return {
        "id": getattr(obj, "getTypeId", lambda: "")() or getattr(obj, "getName", lambda: "")(),
        "name": getattr(obj, "getName", lambda: "")(),
        "type": getattr(obj, "getType", lambda: "")(),
        "typeId": getattr(obj, "getTypeId", lambda: "")(),
    }


def register(context):
    def register_wrapper(f):
        context.getObjectHandler().registerType(f.__name__, f)
        return f

    return register_wrapper


def trigger(context, event, object):
    def trigger_wrapper(f):
        context.getObjectHandler().registerType(f.__name__, f)
        trigger = context.createObject(f.__name__)
        trigger.setStringProperty("object", object)
        trigger.setStringProperty("event", event)
        map = context.getMap()
        if map:
            map.getEventHandler().registerTrigger(trigger)
        return f

    return trigger_wrapper


def list_string(g, list):
    return_list = g.createObject("CListString")
    for item in list:
        return_list.addValue(item)
    return return_list


def player_class_options(g):
    options = {}
    for player_type in sorted(g.getObjectHandler().getAllSubTypes("CPlayer")):
        player = g.createObject(player_type)
        label = player.getStringProperty("label") or player_type
        options[label] = player_type
    return options


def player_race_options(g):
    options = {}
    for race_type in sorted(g.getObjectHandler().getAllSubTypes("CCreatureRace")):
        race = g.createObject(race_type)
        if not race.getBoolProperty("playerSelectable"):
            continue
        label = race.getStringProperty("label") or race_type
        if label in options:
            raise ValueError(
                f"duplicate player-selectable race label {label!r}: "
                f"{options[label]!r} and {race_type!r}"
            )
        options[label] = race_type
    return options


def choose_player_class(g):
    options = player_class_options(g)
    selection = g.getGuiHandler().showSelection(list_string(g, list(options.keys())))
    return options.get(selection, selection)


def race_stat_preview(race):
    # Compact preview of a race's baseStats modifiers for the selection menu,
    # e.g. "STR+1 STA+2 AGI-1 INT-2". Only non-zero deltas are shown; a race that
    # contributes no modifiers (the neutral default) reads as "Balanced".
    base = race.getBaseStats()
    if base is None:
        return "Balanced"
    parts = []
    for name, value in (
        ("STR", base.getStrength()),
        ("AGI", base.getAgility()),
        ("STA", base.getStamina()),
        ("INT", base.getIntelligence()),
    ):
        if value:
            parts.append(f"{name}{value:+d}")
    return " ".join(parts) if parts else "Balanced"


def choose_player_race(g):
    # Offer the player-selectable races (CCreatureRace entries flagged
    # playerSelectable), each labelled with a preview of its stat modifiers so the
    # choice is informed. Returns the chosen race id, or "" when no race is
    # selectable or the choice is cancelled -- an empty race id means "no
    # override", so the player keeps its template's default race and the flow
    # behaves exactly as before races were selectable.
    options = player_race_options(g)
    if not options:
        return ""
    display = {}
    for label, race_type in options.items():
        preview = race_stat_preview(g.createObject(race_type))
        display[f"{label} - {preview}"] = race_type
    selection = g.getGuiHandler().showSelection(list_string(g, sorted(display.keys())))
    return display.get(selection, "")


def choose_character(g):
    # Combined class + race character-creation screen: one panel with two columns
    # of buttons (classes on the left, stat-previewed races on the right), closing
    # once both are picked. Returns (class_type, race_id); an empty class_type means
    # the choice was cancelled. Falls back to the sequential menus when either side
    # has no options (e.g. no player-selectable races), preserving old behaviour.
    class_options = player_class_options(g)  # {label: player_type}
    race_options = player_race_options(g)  # {label: race_type}
    race_display = {}
    for label, race_type in race_options.items():
        preview = race_stat_preview(g.createObject(race_type))
        race_display[f"{label} - {preview}"] = race_type
    if not class_options or not race_display:
        return choose_player_class(g), choose_player_race(g)
    class_label, race_label = g.getGuiHandler().showCharacterCreation(
        list_string(g, list(class_options.keys())),
        list_string(g, list(race_display.keys())),
    )
    if not class_label:
        return "", ""
    return class_options.get(class_label, class_label), race_display.get(race_label, "")


def choose_campaign(g):
    # Stable-ID campaign browser: the GUI lists campaigns by display title while
    # every map stays keyed by the stable campaignId, so duplicate titles cannot
    # collide and the returned value is always a validated stable id. Returns ""
    # when no campaign exists, the browser is cancelled (CANCEL/Escape/close),
    # or an unknown id comes back.
    manifests = campaign.list_campaigns()
    if not manifests:
        g.getGuiHandler().showInfo("No campaigns are available.", True)
        return ""
    titles = g.createObject("CMapStringString")
    titles.setValues({manifest["campaignId"]: manifest["title"] for manifest in manifests})
    descriptions = g.createObject("CMapStringString")
    descriptions.setValues({manifest["campaignId"]: manifest.get("description", "") for manifest in manifests})
    scenario_counts = g.createObject("CMapStringInt")
    scenario_counts.setValues({manifest["campaignId"]: len(manifest["scenarios"]) for manifest in manifests})
    campaign_id = g.getGuiHandler().showCampaignSelection(titles, descriptions, scenario_counts)
    if campaign_id not in {manifest["campaignId"] for manifest in manifests}:
        return ""
    return campaign_id


def new():
    g = CGameLoader.loadGame()
    CGameLoader.loadGui(g)
    selection = g.getGuiHandler().showSelection(list_string(g, ["NEW", "CAMPAIGN", "LOAD", "RANDOM"]))
    if selection == "NEW":
        maps = CResourcesProvider.getInstance().getFiles("MAP")
        if not maps:
            g.getGuiHandler().showInfo("No maps are available.", True)
            return
        map = g.getGuiHandler().showSelection(list_string(g, maps))
        if not map:
            return
        player, race = choose_character(g)
        if not player:
            return
        CGameLoader.startGameWithPlayer(g, map, player, race)
    elif selection == "CAMPAIGN":
        # Resolve the stable campaign id through the browser BEFORE character
        # creation: a cancelled or invalid browse never reaches the class/race
        # chooser.
        campaign_id = choose_campaign(g)
        if not campaign_id:
            return
        player, race = choose_character(g)
        if not player:
            return
        campaign.start(g, campaign_id, player, race)
    elif selection == "LOAD":
        saves = CResourcesProvider.getInstance().getFiles("SAVE")
        if not saves:
            g.getGuiHandler().showInfo("No saved games are available.", True)
            return
        save = g.getGuiHandler().showSelection(list_string(g, saves))
        if not save:
            return
        CGameLoader.loadSavedGame(g, save)
    elif selection == "RANDOM":
        player, race = choose_character(g)
        if not player:
            return
        CGameLoader.startRandomGameWithPlayer(g, player, race)
    while event_loop.instance().run():
        pass


class CDialog(CDialogBase2):
    def _get_public_callback(self, name):
        if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
            return None
        if name in {"invokeAction", "invokeCondition"}:
            return None
        callback = type(self).__dict__.get(name)
        if callback is None:
            return None
        bound = getattr(self, name, None)
        return bound if callable(bound) else None

    def invokeAction(self, action):
        callback = self._get_public_callback(action)
        if callback is None:
            record_playtest_trace(
                "dialog_action_rejected",
                action=action,
                dialog=playtest_object_ref(self),
                reason="unknown_action",
            )
            logger(f"Rejected unknown dialog action: {action}")
            return
        try:
            record_playtest_trace("dialog_action", action=action, dialog=playtest_object_ref(self))
            callback()
        except Exception as exc:
            record_playtest_trace(
                "dialog_action_failed",
                action=action,
                dialog=playtest_object_ref(self),
                error=type(exc).__name__,
            )
            logger(f"Dialog action failed closed: {action}: {exc}")

    def invokeCondition(self, condition):
        callback = self._get_public_callback(condition)
        if callback is None:
            record_playtest_trace(
                "dialog_condition_rejected",
                condition=condition,
                dialog=playtest_object_ref(self),
                reason="unknown_condition",
            )
            logger(f"Rejected unknown dialog condition: {condition}")
            return False
        try:
            result = bool(callback())
            record_playtest_trace(
                "dialog_condition",
                condition=condition,
                dialog=playtest_object_ref(self),
                result=result,
            )
            return result
        except Exception as exc:
            record_playtest_trace(
                "dialog_condition_failed",
                condition=condition,
                dialog=playtest_object_ref(self),
                error=type(exc).__name__,
            )
            logger(f"Dialog condition failed closed: {condition}: {exc}")
            return False
