#pragma once
#include "CGlobal.h"

class CScriptHandler {
public:
    CScriptHandler ();
    ~CScriptHandler();
    void executeScript ( QString script ,boost::python::object nameSpace=boost::python::object() );
    void executeCommand ( std::initializer_list<QString> list );
    QString buildCommand ( std::initializer_list<QString> list );
    void addModule ( QString modName,QString path );
    template <typename... Args>
    std::function<void ( Args... ) > addFunction ( QString functionName, QString functionCode, std::initializer_list<QString> args ) {
        if ( sizeof... ( Args ) !=args.size() ) {
            qFatal ( "Wrong argument list!" );
        }
        QString def ( "def "+functionName+"("+QStringList ( args ).join ( "," )+"):" );
        std::stringstream stream;
        stream<<def.toStdString() <<std::endl;
        for ( QString line:functionCode.split ( "\n" ) ) {
            stream<<"\t"<<line.toStdString() <<std::endl;
        }
        executeScript ( QString::fromStdString ( stream.str() ) );
        boost::python::object func=getObject ( functionName );
        return [func] ( Args... args ) {
            func ( boost::ref ( args )... );
        };
    }
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
    boost::python::object main_module;
    boost::python::object main_namespace;
};

extern "C" {
    PyObject* PyInit__game();
    PyObject* PyInit__core();
}
