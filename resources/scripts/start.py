import sys
from _core import ScriptLoader
sys.meta_path=[]
sys.meta_path.append(ScriptLoader())
sys.dont_write_bytecode=True
sys.path.append('./scripts')
import game
print("I AM BUNDLE")
