import Game

def onCreate(this):
    return

def onEnter(this):
    if Game.getProperty(this,"enabled"):
        loc=Game.getLocation(Game.getProperty(this,"exit"))
        Game.moveObject("PLAYER",loc[0],loc[1],loc[2])
    return

def onMove(this):
    return

def onDestroy(this):
    return


