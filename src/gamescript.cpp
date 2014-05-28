#include "gamescript.h"
#include <QDebug>
#include <QMetaProperty>
#define METHOD(name) {#name,name,METH_VARARGS,NULL}

PyObject *addObject(PyObject *, PyObject *args)
{
    const char *name;
    int x, y, z;
    PyArg_ParseTuple(args, "siii", &name, &x, &y, &z);
    MapObject *object = MapObject::getMapObject(name);
    if (object) {
        GameScene::getMap()->addObject(object);
        object->moveTo(x, y, z);
    }
    qDebug() << "Added object"<<object->typeName.c_str()<<"with name"<<object->name.c_str()<<"on"<<x<<y<<z<<"\n";
    Py_RETURN_NONE;
}

PyObject *replaceTile(PyObject *, PyObject *args)
{
    const char *name;
    int x, y, z;
    PyArg_ParseTuple(args, "siii", &name, &x, &y, &z);
    GameScene::getMap()->removeTile(x, y, z);
    GameScene::getMap()->addTile(name, x, y, z);
    Py_RETURN_NONE;
}

PyObject *setProperty(PyObject *, PyObject *args)
{
    const char *objectName;
    const char *propertyName;
    const char *propertyValue;
    PyArg_ParseTuple(args, "sss",&objectName, &propertyName, &propertyValue);
    std::string propName=propertyName;
    std::string propValue=propertyValue;
    MapObject *object=GameScene::getMap()->getObjectByName(objectName);
    if(!object){
        Py_RETURN_NONE;
    }
    QMetaProperty metaproperty;
    for(int i=0;i<object->metaObject()->propertyCount();i++){
        metaproperty=object->metaObject()->property(i);
        if(!metaproperty.isUser())continue;
        if(propName.find(metaproperty.name())==0){

        }
    }
    QVariant value;
    switch (metaproperty.type()) {
    case QVariant::Bool:
        if (propValue.find("true") == 0) {
            value = true;
        } else if (propValue.find("false") == 0) {
            value = false;
        } else {
            qDebug() << "Failed to set property" << propertyName << "of" << objectName << "to" << propertyValue << "\n";
            Py_RETURN_NONE;
        }
        break;
    default:
        value = propValue.c_str();
        break;
    }
    if (object->setProperty(propName.c_str(), value)) {
        qDebug() << "Set property" << propertyName << "of" << objectName << "to" << propertyValue << "\n";
    } else {
        qDebug() << "Failed to set property" << propertyName << "of" << objectName << "to" << propertyValue << "\n";
    }
    Py_RETURN_NONE;
}

PyMethodDef GameMethods[] = {
    METHOD(addObject), METHOD(replaceTile), METHOD(setProperty),{NULL, NULL, NULL, NULL}
};
PyModuleDef GameModule = {PyModuleDef_HEAD_INIT, "Game", NULL, -1, GameMethods};
