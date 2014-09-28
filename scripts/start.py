import sys
from _core import ScriptLoader
sys.path=[]
sys.meta_path.append(ScriptLoader())
sys.dont_write_bytecode=True
import game
