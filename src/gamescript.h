#ifndef GAMESCRIPT_H
#define GAMESCRIPT_H
#include "gamescene.h"

PyObject *addObject(PyObject *self, PyObject *args);
PyObject *removeObject(PyObject *self, PyObject *args);
PyObject *replaceTile(PyObject *self, PyObject *args);
PyObject *setProperty(PyObject *self, PyObject *args);
PyObject *incProperty(PyObject *self, PyObject *args);
PyObject *getProperty(PyObject *self, PyObject *args);
PyObject *giveItem(PyObject *self, PyObject *args);
PyObject *takeItem(PyObject *self, PyObject *args);
PyObject *getLocation(PyObject *self, PyObject *args);
PyObject *moveObject(PyObject *self, PyObject *args);

extern PyMethodDef GameMethods[];

extern "C"{
    extern void init_Game();
}
#endif // GAMESCRIPT_H
