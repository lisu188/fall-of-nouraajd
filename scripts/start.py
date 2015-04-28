import sys
from _core import CScriptLoader
sys.path=[]
sys.meta_path.append(CScriptLoader())
sys.dont_write_bytecode=True
import game
