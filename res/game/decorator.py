def register(context):
    def register_wrapper(f):
        context.getObjectHandler().registerType(f.__name__,f)
        return f
    return register_wrapper


def trigger(context,event,object):
    def trigger_wrapper(f):
        context.getObjectHandler().registerType(f.__name__,f)
        trigger=context.createObject(f.__name__)
        context.getEventHandler().registerTrigger(object,event,trigger)
        return f
    return trigger_wrapper