#!/usr/bin/python3
import game

def advance(game, turns):
    current_turn = g.getMap().getNumericProperty('turn')
    for i in range(turns):
        g.getMap().move()
    while g.getMap().getNumericProperty('turn') < turns + current_turn:
        game.CEventLoop.instance().run()

if __name__ == '__main__':
    turns = 1000
    g = game.CGameLoader.loadGame()
    game.CGameLoader.startGame(g, "map1", "Warrior")
    advance(game, turns)
    open("map.json","w").write(game.jsonify(g.getMap().ptr()))
# def printName(ob):
#    print(ob.getStringProperty('name'))
#
# def true(ob):
#    return True
#
# g.getMap().forObjects(printName,true)
