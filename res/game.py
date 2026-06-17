from _game import *

set_logger_sink("disabled", None)


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
    def invokeAction(self, action):
        getattr(self, action)()

    def invokeCondition(self, condition):
        return getattr(self, condition)()
