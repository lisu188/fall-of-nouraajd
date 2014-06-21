import Game
import random

def onCreate(this):
    Game.setProperty(this,"monster","Pritz");
    Game.setProperty(this,"chance",15);
    Game.setProperty(this,"monsters",5);
    Game.setProperty(this,"enabled",True);
    return

def onEnter(this):
    if Game.getProperty(this,"enabled"):
        Game.setProperty(this,"enabled",False);
        location=Game.getLocation(this);
        monster=Game.getProperty(this,"monster")
        for i in range(-1,2):
            for j in range(-1,2):
                if j == 0 and i == 0:
                    continue;
                Game.addObject(monster,location[0]+i,location[1]+j,location[2]);
        Game.removeObject(this);
    return

def onMove(this):
    chance=Game.getProperty(this,"chance");
    monsters=Game.getProperty(this,"monsters");
    monster=Game.getProperty(this,"monster");
    enabled=Game.getProperty(this,"enabled");
    if enabled and monsters >0 and (random.randint(1,100)) <= chance:
        location=Game.getLocation(this);
        Game.addObject(monster,location[0],location[1],location[2]);
        Game.incProperty(this,"monsters",-1);
    return

def onDestroy(this):
    return


