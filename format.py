#! /usr/bin/python3

import tokenize
import os
import platform
import subprocess
import sys
import json
import py_compile
from itertools import chain
sys.dont_write_bytecode=True
from reindent import check

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
        check(file)

def getFileList(dir,ext):
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith("."+ext):
                yield os.path.join(root, file)

def main():
    files = chain(getFileList(DIR,"cpp"),getFileList(DIR,"h"))
    formatJson(getFileList(DIR,"json"))
    formatPython(getFileList(DIR,"py"))
    exe = initialize_exe()
    for file_path in files:
        format_source_code(exe, file_path, ["-A2tOPjn"])

def format_source_code(exe, file_path, options):
    astyle = [exe]+options+[file_path]
    subprocess.Popen(astyle,stdout=subprocess.PIPE).communicate()

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