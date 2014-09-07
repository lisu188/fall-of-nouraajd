#! /usr/bin/python
import os,sys,json,time

os.chdir(os.path.dirname(os.path.realpath(__file__)))

def getFileList(dir,ext):
    list=[]
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith("."+ext):
                list.append(os.path.join(root, file))
    return list

try:
    os.mkdir("gen")
except OSError:
    pass

def getMacroBounds(file,macro):
    lines=open(file).readlines()
    for line in lines:
        if line.find("//"+macro)!=-1:
            start=lines.index(line)
            for line in lines[start:]:
                if line.find("//!"+macro)!=-1:
                    stop=lines.index(line)
                    return (start,stop)
                
def getMacroText(file,macro):
    bounds=getMacroBounds(file,macro)
    return open(file).readlines()[bounds[0]:bounds[1]+1]

def getMacroDefinitions(file):
    macros={}
    lines=open(file).readlines()
    for line in lines:
        if line.startswith("//") and not line.startswith("//!"):
            line=line[2:]
            macros[line.strip()]=getMacroText(file, line.strip())
    return macros
            
for header in getFileList("src", "h"):
    macros =getMacroDefinitions("macro.conf")
    for macro in macros:
        bounds = getMacroBounds(header, macro)
        if bounds:
            lines=open(header).readlines()
            ready=lines[:bounds[0]]+macros[macro]+lines[bounds[1]+1:]                
            if open(header).read()!="".join(ready):
                open(header,"w").write("".join(ready))

if os.path.isfile("gen/prop.h") and os.path.getmtime("classes.json") < os.path.getmtime("gen/prop.h"):
    print("Skipping preprocessor step. Configuration did not change.")
    sys.exit(0)

file=open("gen/prop.h","w")
file.write("#pragma once\n")
config=json.loads(open("classes.json").read())
for clas,props in config.iteritems():
    file.write("\n")
    file.write("#define _"+clas+' \\ \n')
    for prop in props:
        file.write("PROP("+prop['type']+","+prop['name']+","+prop['name'][0].upper()+prop['name'][1:]+")")
        if props.index(prop)==len(props)-1:
            file.write('\n')
        else:
            file.write('\\\n')


