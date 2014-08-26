#! /usr/bin/python

""" ExampleExe.py
    This program calls the Artistic Style executable to format the AStyle source files.
    The Artistic Style executable must be in the same directory as this script.
    It will work with either Python version 2 or 3 (unicode).
"""

# to disable the print statement and use the print() function (version 3 format)
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
        print(out)
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
    """Format file_in by calling the AStyle executable.
       The unicode variables in Version 3 will be changed to
       byte variables by the operating system.
       The astyle messages will not display when run from a
       Windows editor.
    """
    astyle = [exe, options, file_path]
    retval = subprocess.call(astyle)
    if retval:
        print("Bad astyle return: " + str(retval))
        sys.exit(1)


# -----------------------------------------------------------------------------

def initialize_exe():
    """Set the file path and executable name.
       Verify the executable is available.
       Return the executable name.
    """
    # change directory to the path where this script is located
    pydir = sys.path[0]
    os.chdir(pydir)
    # return the executable name for the platform
    if os.name == "nt":
        exe = "AStyle.exe"
    else:
        exe = "/usr/bin/astyle"
    # verify the astyle executable is available
    if not os.path.isfile(exe):
        print("Cannot find", exe)
        sys.exit(1)
    return exe

# -----------------------------------------------------------------------------

# make the module executable
if __name__ == "__main__":
    main()
    sys.exit(0)
