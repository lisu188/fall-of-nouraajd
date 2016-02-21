#!/usr/bin/python3
import game
g=game.CGameLoader.loadGame()
game.CGameLoader.startGame(g,"map1","Warrior")
for i in range(1000000):
    g.getMap().move()
while g.getMap().getNumericProperty('turn')<1000000:
    game.CEventLoop.instance().run()
