from _game import *

def game_object(object):
    from _core import registerType
    registerType(object.__name__,object)
    return object

def game_trigger(map,event,object):
    def trigger_wrapper(f):
        from _core import registerType
        registerType(f.__name__,f)
        trigger=map.getObjectHandler().createObject(f.__name__)
        map.getEventHandler().registerTrigger(object,event,trigger)
        return f
    return trigger_wrapper
