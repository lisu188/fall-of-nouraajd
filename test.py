import game
import unittest
from teamcity import is_running_under_teamcity
from teamcity.unittestpy import TeamcityTestRunner


def game_test(f):
    def wrapper(self):
        n = f.__name__.split("test_")[1]
        result = f(self)
        success = result[0]
        log = result[1]
        open(n + ".log", "w").write(str(log))
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
    def test_all_objects(self):
        failed = []
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGame(g, "empty")
        for type in g.getMap().getObjectHandler().getAllTypes():
            print("Creating: " + type)
            object = g.createObject(type)
            if object:
                print(game.jsonify(object).strip())
            else:
                print("Failed to create: " + type)
                failed.append(type)
        return failed == [], failed

    @game_test
    def test_run_turns(self):
        g = game.CGameLoader.loadGame()
        game.CGameLoader.startGameWithPlayer(g, "map1", "Warrior")
        advance(g, 1000)  # TODO: set value from build
        return True, game.jsonify(g.getMap().ptr())  # TODO: why we need ptr? in all _bjects we dont!

if __name__ == '__main__':
    if is_running_under_teamcity():
        runner = TeamcityTestRunner()
    else:
        input()
        runner = unittest.TextTestRunner()
    unittest.main(testRunner=runner)
