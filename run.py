#!/usr/bin/python3
import game
g=game.CGameLoader.loadGame()
game.CGameLoader.startGame(g,"map1","Warrior")
g.getMap().move()