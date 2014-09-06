#! /usr/bin/python
import os,sys,json,time

os.chdir(os.path.dirname(os.path.realpath(__file__)))

try:
    os.mkdir("gen")
except OSError:
    pass

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


