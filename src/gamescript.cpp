#include "gamescript.h"
#include <QDebug>

PyObject* Game_addObject(PyObject *, PyObject *args)
{
    const char *name;
    int x,y,z;
    PyArg_ParseTuple(args,"siii",&name,&x,&y,&z);
    MapObject *object=MapObject::getMapObject(name);
    if(object){
        GameScene::getMap()->addObject(object);
        object->moveTo(x,y,z);
    }
    Py_RETURN_NONE;
}

PyMethodDef GameMethods[]={
    {"addObject",Game_addObject,METH_VARARGS}, {NULL, NULL, 0, NULL}
};
PyModuleDef GameModule={PyModuleDef_HEAD_INIT,"Game",NULL,-1,GameMethods};
