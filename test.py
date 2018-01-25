import json
import unittest

import game


def game_test(f):
    def wrapper(self):
        n = f.__name__.split("test_")[1]
        result = f(self)
        success = result[0]
        log = result[1]
        open(n + ".json", "w").write(str(log))
        self.assertTrue(success)

    return wrapper


def advance(g, turns):
    current_turn = g.getMap().getNumericProperty('turn')
    for i in range(turns):
        g.getMap().move()
    while g.getMap().getNumericProperty('turn') < turns + current_turn:
        game.CEventLoop.instance().run()


class GameTest(unittest.TestCase):
    @game_test
    def test_objects(self):
        failed = []
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        for type in g.getMap().getObjectHandler().getAllTypes():
            object = g.getMap().createObject(type)
            if not object:
                failed.append(type)
        return failed == [], failed

    @game_test
    def test_fights(self):
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        creatures = g.getMap().getObjectHandler().getAllSubTypes("CCreature")
        values = []
        for type1 in creatures:
            for type2 in creatures:
                object1 = g.getMap().createObject(type1)
                object2 = g.getMap().createObject(type2)
                g.getMap().addObject(object1)
                g.getMap().addObject(object2)
                if not game.CFightHandler.fight(object1, object2):
                    values.append((type1, type2, "none"))
                if object1.isAlive() and not object2.isAlive():
                    values.append((type1, type2, "first"))
                if object2.isAlive() and not object1.isAlive():
                    values.append((type1, type2, "second"))
                if not object1.isAlive() and not object2.isAlive():
                    values.append((type1, type2, "both"))
        return True, json.dumps(values)

    @game_test
    def test_level(self):
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        creatures = g.getMap().getObjectHandler().getAllSubTypes("CCreature")
        values = []
        for type1 in creatures:
            object = g.getMap().createObject(type1)
            g.getMap().addObject(object)
            while object.getLevel() < 25:
                object.addExp(1000)
            values.append(json.loads(game.jsonify(object)))
        return True, json.dumps(values)

    @game_test
    def test_turns(self):
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "map1", "Warrior")
        advance(g, 100)  # TODO: set value from build
        return True, game.jsonify(g.getMap().ptr())  # TODO: why we need ptr? in all _bjects we dont!

    @game_test
    def test_pathfinder(self):
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "map1", "Warrior")
        g.getMap().dumpPaths("pathfinder.png")


if __name__ == '__main__':
    unittest.main(testRunner=unittest.TextTestRunner())
