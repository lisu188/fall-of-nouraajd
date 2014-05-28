#ifndef GAMESCRIPT_H
#define GAMESCRIPT_H
#include "gamescene.h"

PyObject *addObject(PyObject *, PyObject *args);
PyObject *removeObject(PyObject *, PyObject *args);
PyObject *replaceTile(PyObject *, PyObject *args);
PyObject *setProperty(PyObject *, PyObject *args);
PyObject *giveItem(PyObject *, PyObject *args);
PyObject *takeItem(PyObject *, PyObject *args);

extern PyMethodDef GameMethods[];

extern PyModuleDef GameModule;
#endif // GAMESCRIPT_H
