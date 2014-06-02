import random;

def onCreate():
    setProperty(THIS,"monster","Pritz");
    setProperty(THIS,"chance",15);
    setProperty(THIS,"monsters",5);
    setProperty(THIS,"enabled",true);
    return;

def onEnter():
    if getProperty(THIS,"enabled"):
        setProperty(THIS,"enabled",false);
        location=getLocation(THIS);
        for i in range(-1,2):
            for j in range(-1,2):
                if j == 0 and i == 0:
                    continue;
                addObject(monster,location[0]+i,location[1]+j,location[2]);
        removeObject(THIS);
    return;

def onMove():
    chance=getProperty(THIS,"chance");
    monsters=getProperty(THIS,"monsters");
    monster=getProperty(THIS,"monster");
    enabled=getProperty(THIS,"enabled");
    if enabled and monsters >0 and (random.randint(0,99)) <= chance and monsters > 0:
        location=getLocation(THIS);
        addObject(monster,location[0],location[1],location[2]);
        incProperty(THIS,"monsters",-1);
    return;

def onDestroy():
    return;

