from _game import *
from . import interaction
from . import object
from . import effect

def switchClass(object,cls):
    if(cls):
        object.__class__=cls
