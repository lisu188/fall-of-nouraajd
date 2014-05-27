#ifndef GAMESCRIPT_H
#define GAMESCRIPT_H
#include "gamescene.h"

PyObject *Game_addObject(PyObject *, PyObject *args);

extern PyMethodDef GameMethods[];

extern PyModuleDef GameModule;
#endif // GAMESCRIPT_H
