import game

if __name__ == '__main__':
    g = game.CGameLoader.loadGame()
    game.CGameLoader.startGame(g, "empty")
    for type in g.getObjectHandler().getAllTypes():
        g.getObjectHandler().createObject(type)