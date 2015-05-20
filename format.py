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
IGNORED=["map.json"]

# -----------------------------------------------------------------------------

def sortHeader():
    lines=open("CGlobal.h", "r").readlines()[1:]
    l=set()
    for line in lines:
        l.add(line.strip())
    with open("CGlobal.h", "w") as sortToFile:
        sortToFile.write("#pragma once\n")
        for line in sorted(l, key = str.lower):
            if len(line.strip()) >0:
                sortToFile.write(line+"\n")

def formatJson(files):
    for file in files:
        text=open(file).read()
        try:
            out=json.dumps(json.loads(text), sort_keys = True, indent = 4)
            if out!=text:
                open(file,"w").write(out)
        except:
            print("Error:",file)

def formatPython(files):
    for file in files:
        py_compile.compile(file,doraise=True)
        check(file)

def getFileList(dir,ext):
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith("."+ext) and not file in IGNORED:
                yield os.path.join(root, file)

def main():
    files = chain(getFileList(DIR,"cpp"),getFileList(DIR,"h"))
    formatJson(getFileList(DIR,"json"))
    formatPython(getFileList(DIR,"py"))
    sortHeader()
    for file_path in files:
        format_source_code("astyle", file_path, ["-A2s4OPjn"])

def format_source_code(exe, file_path, options):
    astyle = [exe]+options+[file_path]
    subprocess.Popen(astyle,stdout=subprocess.PIPE).communicate()

if __name__ == "__main__":
    main()
