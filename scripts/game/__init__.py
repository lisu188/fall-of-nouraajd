from _game import *
from . import interaction
from . import object
from . import effect
from . import tile
from . import potion

def switchClass(object,cls):
    if cls and type(cls) != float:
        object.__class__=cls

def game_object(object):
    from _core import registerType
    registerType(object.__name__,object)
    return object

def game_trigger(event,object):
    def trigger_wrapper(f):
        pass
    return trigger_wrapper
