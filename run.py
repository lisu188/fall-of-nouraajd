#!/usr/bin/python3
import game
g=game.CGameLoader.loadGame()
game.CGameLoader.startGame(g,"map1","Warrior")
for i in range(1000000):
    g.getMap().move()
    game.CEventLoop.instance().run()
while True:
    game.CEventLoop.instance().run()
