#include <boost/python.hpp>
#include "gamescript.h"
#include <src/building.h>
#include <src/interaction.h>
#include <src/stats.h>
#include <string>
#include <QMetaProperty>
#define METHOD(name) {#name,name,METH_VARARGS,NULL}

namespace {
// The ScriptEngine publishes its Map as a hexadecimal pointer string in __main__.map.
Map *scriptMap() {
    PyObject *main = PyImport_ImportModule("__main__");
    PyObject *value = main ? PyObject_GetAttrString(main, "map") : NULL;
    Map *map = NULL;
    if (value && PyString_Check(value)) {
        map = (Map *)std::stoul(PyString_AsString(value), 0, 16);
    }
    Py_XDECREF(value);
    Py_XDECREF(main);
    return map;
}
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
    const char *propertyValue;
    PyArg_ParseTuple(args, "sss",&objectName, &propertyName, &propertyValue);
    std::string propName=propertyName;
    std::string propValue=propertyValue;
    MapObject *object=scriptMap()->getObjectByName(objectName);
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
            Py_RETURN_NONE;
        }
        break;
    default:
        value = propValue.c_str();
        break;
    }
    if (object->setProperty(propName.c_str(), value)) {
    } else {
    }
    Py_RETURN_NONE;
}

PyMethodDef GameMethods[] = {
    METHOD(addObject), METHOD(replaceTile), METHOD(setProperty),{NULL, NULL, NULL, NULL}
};

BOOST_PYTHON_MODULE(_Game)
{
    boost::python::class_<Building, boost::noncopyable>("Building", boost::python::no_init);
    boost::python::class_<Damage>("Damage")
        .add_property("fire", &Damage::getFire, &Damage::setFire)
        .add_property("frost", &Damage::getFrost, &Damage::setFrost)
        .add_property("thunder", &Damage::getThunder, &Damage::setThunder)
        .add_property("normal", &Damage::getNormal, &Damage::setNormal)
        .add_property("shadow", &Damage::getShadow, &Damage::setShadow);
    boost::python::class_<Interaction, boost::noncopyable>("Interaction", boost::python::no_init);
}
