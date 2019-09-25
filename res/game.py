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


def new(map):
    g = CGameLoader.loadGame()
    CGameLoader.loadGui(g)
    player = g.getGuiHandler().showSelection(list_string(g, g.getObjectHandler().getAllSubTypes("CPlayer")))
    CGameLoader.startGameWithPlayer(g, map, player)
    while event_loop.instance().run():
        pass


def load(save):
    g = CGameLoader.loadGame()
    CGameLoader.loadGui(g)
    CGameLoader.loadSavedGame(g, save)
    while event_loop.instance().run():
        pass
