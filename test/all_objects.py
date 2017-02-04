import game

# TODO: add mechanism to detect not registered types in v_meta
if __name__ == '__main__':
    g = game.CGameLoader.loadGame()
    game.CGameLoader.startGame(g,"empty")
    for type in g.getMap().getObjectHandler().getAllTypes():
        print("Creating: " + type)
        object = g.createObject(type)
        if object:
            print(game.jsonify(object).strip())
        else:
            print("Failed to create: " + type)
