#ifndef GAMESCRIPT_H
#define GAMESCRIPT_H
#include "gamescene.h"

PyObject *addObject(PyObject *, PyObject *args);
PyObject *removeObject(PyObject *, PyObject *args);
PyObject *replaceTile(PyObject *, PyObject *args);
PyObject *setProperty(PyObject *, PyObject *args);
PyObject *incProperty(PyObject *, PyObject *args);
PyObject *decProperty(PyObject *, PyObject *args);
PyObject *getProperty(PyObject *, PyObject *args);
PyObject *giveItem(PyObject *, PyObject *args);
PyObject *takeItem(PyObject *, PyObject *args);
PyObject *getObjectLocation(PyObject *, PyObject *args);

extern PyMethodDef GameMethods[];

extern PyModuleDef GameModule;
#endif // GAMESCRIPT_H
