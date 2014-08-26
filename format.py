#! /usr/bin/python

from __future__ import print_function

import os
import platform
import subprocess
import sys
import json
# -----------------------------------------------------------------------------

def formatJson(files):
    for file in files:
        out=json.dumps(json.loads(open(file).read()), sort_keys = True, indent = 4)
        open(file,"w").write(out)

def getFileList(dir,ext):
    list=[]
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith("."+ext):
                list.append(os.path.join(root, file))
    return list

def main():
    """Main processing function.
    """
    files = getFileList(".","cpp")+getFileList(".","h")
    options = "-A2tOP"

    jsonFiles=getFileList(".","json")
    formatJson(jsonFiles)

    #initialization
    print("ExampleExe",
          platform.python_implementation(),
          platform.python_version(),
          platform.architecture()[0])
    exe = initialize_exe()
    display_astyle_version(exe)
    # process the input files
    for file_path in files:
        format_source_code(exe, file_path, options)

# -----------------------------------------------------------------------------

def display_astyle_version(exe):
    """Display the version number from the AStyle executable.
       This will not display when run from a Windows editor.
    """
    astyle = [exe, "--version"]
    retval = subprocess.call(astyle)
    if retval:
        print("Bad astyle return: " + str(retval))
        sys.exit(1)

# -----------------------------------------------------------------------------

def format_source_code(exe, file_path, options):
    astyle = [exe, options, file_path]
    retval = subprocess.call(astyle)
    if retval:
        print("Bad astyle return: " + str(retval))
        sys.exit(1)


# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------

# make the module executable
if __name__ == "__main__":
    main()
    sys.exit(0)
