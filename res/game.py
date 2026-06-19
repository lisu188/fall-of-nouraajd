from _game import *
import json

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


def choose_player_class(g):
    options = player_class_options(g)
    selection = g.getGuiHandler().showSelection(list_string(g, list(options.keys())))
    return options.get(selection, selection)


def new():
    g = CGameLoader.loadGame()
    CGameLoader.loadGui(g)
    selection = g.getGuiHandler().showSelection(list_string(g, ["NEW", "LOAD", "RANDOM"]))
    if selection == "NEW":
        maps = CResourcesProvider.getInstance().getFiles("MAP")
        if not maps:
            g.getGuiHandler().showInfo("No maps are available.", True)
            return
        map = g.getGuiHandler().showSelection(list_string(g, maps))
        if not map:
            return
        player = choose_player_class(g)
        CGameLoader.startGameWithPlayer(g, map, player)
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
        player = choose_player_class(g)
        CGameLoader.startRandomGameWithPlayer(g, player)
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
