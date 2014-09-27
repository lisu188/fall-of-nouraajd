#! /usr/bin/python3
from __future__ import print_function

import tokenize
import os
import platform
import subprocess
import sys
import json
import py_compile
sys.dont_write_bytecode=True

os.chdir(os.path.dirname(os.path.realpath(__file__)))

DIR="."
# -----------------------------------------------------------------------------

def formatJson(files):
    for file in files:
        text=open(file).read()
        out=json.dumps(json.loads(text), sort_keys = True, indent = 4)
        if(out!=text):
            open(file,"w").write(out)

def formatPython(files):
    for file in files:
        py_compile.compile(file,doraise=True)

def getFileList(dir,ext):
    list=[]
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith("."+ext):
                list.append(os.path.join(root, file))
    return list

def main():
    files = getFileList(DIR,"cpp")+getFileList(DIR,"h")
    formatJson(getFileList(DIR,"json"))
    formatPython(getFileList(DIR,"py"))
    exe = initialize_exe()
    for file_path in files:
        format_source_code(exe, file_path, ["-A2tOPj"])

def format_source_code(exe, file_path, options):
    astyle = [exe]+options+[file_path]
    subprocess.Popen(astyle,stdout=subprocess.PIPE)

def initialize_exe():
    pydir = sys.path[0]
    os.chdir(pydir)
    if os.name == "nt":
        exe = "AStyle.exe"
    else:
        exe = "/usr/bin/astyle"
    if not os.path.isfile(exe):
        print("Cannot find", exe)
        sys.exit(1)
    return exe

if __name__ == "__main__":
    main()
    sys.exit(0)
