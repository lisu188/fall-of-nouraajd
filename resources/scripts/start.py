import sys
from _core import ScriptLoader
sys.meta_path.append(ScriptLoader())
sys.dont_write_bytecode=True
import game
for i in range(1000):
    print(game.randint(0,100))
