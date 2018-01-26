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


def main():
    g = CGameLoader.loadGame()
    CGameLoader.startGameWithPlayer(g, "map1", "Warrior")
    CGameLoader.loadGui(g)
    while CEventLoop.instance().run():
        pass


def load(save):
    g = CGameLoader.loadGame()
    CGameLoader.loadSavedGame(g, save)
    CGameLoader.loadGui(g)
    while CEventLoop.instance().run():
        pass
