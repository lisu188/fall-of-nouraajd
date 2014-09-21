#pragma once
#include <QObject>
#include <string>
#include <boost/python.hpp>
#define PY_UNSAFE(FUNC) try{FUNC}catch(...){PyErr_Print();throw;}

class CMap;

class CScriptEngine :public QObject {
	Q_OBJECT
public:
	static CScriptEngine *getInstance();
	void executeScript ( QString script , QString nameSpace="" );
	void executeCommand ( std::initializer_list<QString> list );
	QString buildCommand ( std::initializer_list<QString> list );
	boost::python::object getObject ( QString name );
	CScriptEngine ();
	~CScriptEngine();
	template<typename ...T>
	void callFunction ( QString nameSpace,QString name,T ... params ) {
		main_namespace[nameSpace][name] ( params... );
	}
	template<typename T>
	T createObject ( QString clas ) {
		PY_UNSAFE (
		    QString script="object=";
		    script=script.append ( clas );
		    script=script.append ( "()" );
		    executeScript (  script );
		    boost::python::object object= main_namespace["object"];
		    boost::python::incref ( object.ptr() );
		    return boost::python::extract<T> ( object ); )
	}
private:
	boost::python::object main_module;
	boost::python::object main_namespace;
};

extern "C" {
	PyObject* PyInit__game();
}

