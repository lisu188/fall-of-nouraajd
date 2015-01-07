#!/usr/local/bin/python3
from subprocess import Popen,PIPE
import os
import sys

QMAKE_ARGS=['-r','-spec','linux-g++']
QMAKE_ARGS_DEBUG=['CONFIG+=debug']

if __name__=='__main__':
    if len(sys.argv)!=2 or (not '-r' in sys.argv and not '-d' in sys.argv) or ('-r' in sys.argv and '-d' in sys.argv):
        print('-r release')
        print('-d debug')
    else:
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        import format
        format.main()
        try:
            os.mkdir("../game-build")
        except:
            pass
        os.chdir("../game-build")
        Popen(['qmake','../game/game.pro']+QMAKE_ARGS+(QMAKE_ARGS_DEBUG if '-d' in sys.argv else [])).communicate()
        Popen(['make','-j4']).communicate()
        if '-r' in sys.argv:
            Popen(['strip','game']).communicate()
        os.chdir("../game")
        Popen(['git','clean','-xdf']).communicate()
        Popen(['cloc','.','--exclude-dir=boost','--exclude-lang=JSON,IDL','--force-lang=C++,h']).communicate()
