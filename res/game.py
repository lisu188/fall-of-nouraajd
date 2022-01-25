from _game import *


def register(context):
    def register_wrapper(f):
        context.getObjectHandler().registerType(f.__name__, f)
        return f

    return register_wrapper


def trigger(context, event, object):
    def trigger_wrapper(f):
        context.getObjectHandler().registerType(f.__name__, f)
        trigger = context.createObject(f.__name__)
        trigger.setStringProperty('object', object)
        trigger.setStringProperty('event', event)
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


def new():
    g = CGameLoader.loadGame()
    CGameLoader.loadGui(g)
    selection = g.getGuiHandler().showSelection(list_string(g, ["NEW", "LOAD", "RANDOM"]))
    if selection == "NEW":
        map = g.getGuiHandler().showSelection(list_string(g, CResourcesProvider.getInstance().getFiles("MAP")))
        player = g.getGuiHandler().showSelection(list_string(g, g.getObjectHandler().getAllSubTypes("CPlayer")))
        CGameLoader.startGameWithPlayer(g, map, player)
    elif selection == "LOAD":
        save = g.getGuiHandler().showSelection(list_string(g, CResourcesProvider.getInstance().getFiles("SAVE")))
        CGameLoader.loadSavedGame(g, save)
    elif selection == "RANDOM":
        player = g.getGuiHandler().showSelection(list_string(g, g.getObjectHandler().getAllSubTypes("CPlayer")))
        CGameLoader.startRandomGameWithPlayer(g, player)
    while event_loop.instance().run():
        pass


class CDialog(CDialogBase2):
    def invokeAction(self, action):
        getattr(self, action)()

    def invokeCondition(self, condition):
        return getattr(self, condition)()
