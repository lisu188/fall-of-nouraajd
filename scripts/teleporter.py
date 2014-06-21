def onCreate():
    return

def onEnter():
    if getProperty(THIS,"enabled"):
        loc=getLocation(getProperty(THIS,"exit"))
        moveObject("PLAYER",loc[0],loc[1],loc[2])
    return

def onMove():
    return

def onDestroy():
    return


