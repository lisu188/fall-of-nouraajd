from _game import *

def load(context):
    pass

def register(context):
    def register_wrapper(f):
        context.getObjectHandler().registerType(f.__name__,f)
        return f
    return register_wrapper


def trigger(context,event,object):
    def trigger_wrapper(f):
        context.getEventHandler().registerTrigger(object,event,f)
        return f
    return trigger_wrapper
