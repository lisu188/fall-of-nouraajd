#pragma once
#include <boost/python.hpp>

class CScriptHandler {
public:
    static CScriptHandler* getInstance();
    void executeScript ( QString script ,boost::python::object nameSpace=boost::python::object() );
    void executeCommand ( std::initializer_list<QString> list );
    QString buildCommand ( std::initializer_list<QString> list );
    void addModule ( QString modName,QString path );
    template<typename T=boost::python::object>
    T getObject ( QString name ) {
        try {
            QString script="object=";
            script=script.append ( name );
            executeScript (  script );
            boost::python::object object= main_namespace["object"];
            return boost::python::extract<T> ( object );
        } catch ( ... ) {
            PyErr_Clear();
            return boost::python::object();
        }
    }
    template<typename ...T>
    void callFunction ( QString name,T ... params ) {
        QString script="object=";
        script=script.append ( name );
        executeScript (  script );
        boost::python::object object= main_namespace["object"];
        object ( params... );
    }
    template<typename T>
    T createObject ( QString clas ) {
        QString script="object=";
        script=script.append ( clas );
        script=script.append ( "()" );
        executeScript (  script );
        boost::python::object object= main_namespace["object"];
        boost::python::incref ( object.ptr() );
        return boost::python::extract<T> ( object );
    }
private:
    CScriptHandler (  );
    ~CScriptHandler();
    boost::python::object main_module;
    boost::python::object main_namespace;
};

extern "C" {
    PyObject* PyInit__game();
    PyObject* PyInit__core();
}
