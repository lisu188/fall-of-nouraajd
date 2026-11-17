#include "gamescript.h"
#include <QDebug>
#include <QMetaProperty>
#define METHOD(name) {#name,name,METH_VARARGS,NULL}

PyObject *addObject(PyObject *, PyObject *args)
{
    const char *name;
    int x, y, z;
    PyArg_ParseTuple(args, "siii", &name, &x, &y, &z);
    MapObject *object = MapObject::createMapObject(name);
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

PyObject *incProperty(PyObject *, PyObject *args)
{
    const char *objectName;
    const char *propertyName;
    int value;
    PyArg_ParseTuple(args, "ssi", &objectName, &propertyName, &value);
    MapObject *object = GameScene::getMap()->getObjectByName(objectName);
    if (object) {
        object->setProperty(propertyName, object->property(propertyName).toInt() + value);
    }
    Py_RETURN_NONE;
}

PyObject *moveObject(PyObject *, PyObject *args)
{
    const char *name;
    int x, y, z;
    PyArg_ParseTuple(args, "siii", &name, &x, &y, &z);
    MapObject *object = GameScene::getMap()->getObjectByName(name);
    if (object) {
        object->moveTo(x, y, z);
    }
    Py_RETURN_NONE;
}

PyObject *getProperty(PyObject *, PyObject *args)
{
    const char *objectName;
    const char *propertyName;
    PyArg_ParseTuple(args, "ss", &objectName, &propertyName);
    MapObject *object = GameScene::getMap()->getObjectByName(objectName);
    if (!object) {
        Py_RETURN_NONE;
    }
    QVariant value = object->property(propertyName);
    switch (value.type()) {
    case QVariant::Invalid:
        Py_RETURN_NONE;
    case QVariant::Bool:
        return PyBool_FromLong(value.toBool());
    case QVariant::Int:
        return PyLong_FromLong(value.toInt());
    default:
        return PyUnicode_FromString(value.toString().toStdString().c_str());
    }
}

PyObject *removeObject(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    MapObject *object = GameScene::getMap()->getObjectByName(name);
    if (object) {
        GameScene::getMap()->removeObject(object);
    }
    Py_RETURN_NONE;
}

PyObject *giveItem(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    Item *item = Item::createItem(name);
    if (item) {
        GameScene::getPlayer()->addItem(item);
    }
    Py_RETURN_NONE;
}

PyObject *takeItem(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    std::set<Item *> *inventory = GameScene::getPlayer()->getInventory();
    for (std::set<Item *>::iterator it = inventory->begin(); it != inventory->end(); it++) {
        if ((*it)->typeName.compare(name) == 0) {
            GameScene::getPlayer()->loseItem(*it);
            break;
        }
    }
    Py_RETURN_NONE;
}

PyObject *getLocation(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    MapObject *object = GameScene::getMap()->getObjectByName(name);
    if (!object) {
        Py_RETURN_NONE;
    }
    return Py_BuildValue("(iii)", object->getPosX(), object->getPosY(), object->getPosZ());
}

PyMethodDef GameMethods[] = {
    METHOD(addObject), METHOD(removeObject), METHOD(replaceTile), METHOD(setProperty), METHOD(incProperty), METHOD(getProperty), METHOD(moveObject), METHOD(giveItem), METHOD(takeItem), METHOD(getLocation), {NULL, NULL, NULL, NULL}
};
PyModuleDef GameModule = {PyModuleDef_HEAD_INIT, "Game", NULL, -1, GameMethods};
