from _game import *
from . import interaction
from . import object
from . import effect
from . import tile
from . import potion

def switchClass(object,cls):
    if cls and type(cls) != float:
        object.__class__=cls
