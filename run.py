#!/usr/bin/python3
import game

turns = 1000000
g=game.CGameLoader.loadGame()
g.setBoolProperty('auto_save', True)
game.CGameLoader.startGame(g,"map1","Warrior")
for i in range(turns):
    g.getMap().move()
while g.getMap().getNumericProperty('turn') < turns:
    game.CEventLoop.instance().run()

# def printName(ob):
#    print(ob.getStringProperty('name'))
#
# def true(ob):
#    return True
#
# g.getMap().forObjects(printName,true)
