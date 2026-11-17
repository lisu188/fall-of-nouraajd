#include "gamescript.h"
#include "util.h"
#include <cstdlib>
#include <QDebug>
#include <QMetaProperty>
#define METHOD(name) {#name,name,METH_VARARGS,NULL}

// Scripts act on the map whose engine runs them; the engine stores that map's address in __main__.map.
static Map *scriptMap()
{
    PyObject *value = PyObject_GetAttrString(PyImport_AddModule("__main__"), "map");
    if (!value) {
        PyErr_Clear();
        return 0;
    }
    Map *map = (Map *)strtoul(PyUnicode_AsUTF8(value), 0, 16);
    Py_DECREF(value);
    return map;
}

PyObject *addObject(PyObject *, PyObject *args)
{
    const char *name;
    int x, y, z;
    PyArg_ParseTuple(args, "siii", &name, &x, &y, &z);
    MapObject *object = MapObject::createMapObject(name);
    if (object) {
        scriptMap()->addObject(object);
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
    scriptMap()->removeTile(x, y, z);
    scriptMap()->addTile(name, x, y, z);
    Py_RETURN_NONE;
}

PyObject *setProperty(PyObject *, PyObject *args)
{
    const char *objectName;
    const char *propertyName;
    PyObject *propertyObject;
    if (!PyArg_ParseTuple(args, "ssO", &objectName, &propertyName, &propertyObject)) {
        return NULL;
    }
    PyObject *text = PyObject_Str(propertyObject);
    if (!text) {
        return NULL;
    }
    std::string propName = propertyName;
    std::string propValue = PyUnicode_AsUTF8(text);
    Py_DECREF(text);
    MapObject *object = scriptMap()->getObjectByName(objectName);
    if (!object) {
        Py_RETURN_NONE;
    }
    int type = QVariant::Invalid;
    for (int i = 0; i < object->metaObject()->propertyCount(); i++) {
        QMetaProperty metaproperty = object->metaObject()->property(i);
        if (metaproperty.isUser() && propName.compare(metaproperty.name()) == 0) {
            type = metaproperty.type();
            break;
        }
    }
    QVariant value;
    int number;
    bool isBool = propValue.compare("True") == 0 || propValue.compare("False") == 0;
    switch (type) {
    case QVariant::Bool:
        if (!isBool) {
            qDebug() << "Failed to set property" << propertyName << "of" << objectName << "to" << propValue.c_str() << "\n";
            Py_RETURN_NONE;
        }
        value = propValue.compare("True") == 0;
        break;
    case QVariant::Int:
        if (!str2int(number, propValue.c_str())) {
            qDebug() << "Failed to set property" << propertyName << "of" << objectName << "to" << propValue.c_str() << "\n";
            Py_RETURN_NONE;
        }
        value = number;
        break;
    case QVariant::Invalid:
        if (isBool) {
            value = propValue.compare("True") == 0;
        } else if (str2int(number, propValue.c_str())) {
            value = number;
        } else {
            value = QString::fromStdString(propValue);
        }
        break;
    default:
        value = QString::fromStdString(propValue);
        break;
    }
    object->setProperty(propName.c_str(), value);
    qDebug() << "Set property" << propertyName << "of" << objectName << "to" << propValue.c_str() << "\n";
    Py_RETURN_NONE;
}

PyObject *incProperty(PyObject *, PyObject *args)
{
    const char *objectName;
    const char *propertyName;
    int value;
    PyArg_ParseTuple(args, "ssi", &objectName, &propertyName, &value);
    MapObject *object = scriptMap()->getObjectByName(objectName);
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
    MapObject *object = scriptMap()->getObjectByName(name);
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
    MapObject *object = scriptMap()->getObjectByName(objectName);
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
    MapObject *object = scriptMap()->getObjectByName(name);
    if (object) {
        scriptMap()->removeObject(object);
    }
    Py_RETURN_NONE;
}

PyObject *giveItem(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    Item *item = Item::createItem(name);
    if (item) {
        scriptMap()->getScene()->getPlayer()->addItem(item);
    }
    Py_RETURN_NONE;
}

PyObject *takeItem(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    std::set<Item *> *inventory = scriptMap()->getScene()->getPlayer()->getInventory();
    for (std::set<Item *>::iterator it = inventory->begin(); it != inventory->end(); it++) {
        if ((*it)->typeName.compare(name) == 0) {
            scriptMap()->getScene()->getPlayer()->removeFromInventory(*it);
            break;
        }
    }
    Py_RETURN_NONE;
}

PyObject *getLocation(PyObject *, PyObject *args)
{
    const char *name;
    PyArg_ParseTuple(args, "s", &name);
    MapObject *object = scriptMap()->getObjectByName(name);
    if (!object) {
        Py_RETURN_NONE;
    }
    return Py_BuildValue("(iii)", object->getPosX(), object->getPosY(), object->getPosZ());
}

PyMethodDef GameMethods[] = {
    METHOD(addObject), METHOD(removeObject), METHOD(replaceTile), METHOD(setProperty), METHOD(incProperty), METHOD(getProperty), METHOD(moveObject), METHOD(giveItem), METHOD(takeItem), METHOD(getLocation), {NULL, NULL, NULL, NULL}
};
PyModuleDef GameModule = {PyModuleDef_HEAD_INIT, "Game", NULL, -1, GameMethods};
