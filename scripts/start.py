import sys
from _core import CGeneralLoader
sys.path=[]
sys.meta_path.append(CGeneralLoader())
sys.dont_write_bytecode=True
import game
