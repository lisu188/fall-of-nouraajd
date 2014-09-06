#pragma once
#include <QObject>
#include <string>
#include <boost/python.hpp>
#define PY_UNSAFE(FUNC) try{FUNC}catch(...){PyErr_Print();throw;}

class CMap;

class CScriptEngine {
public:
	void executeScript ( QString script );
	void executeCommand ( std::initializer_list<QString> list );
	QString buildCommand ( std::initializer_list<QString> list );
	boost::python::object getObject ( QString name );
	CScriptEngine ();
	~CScriptEngine();
	template<typename T>
	T createObject ( QString clas ) {
		PY_UNSAFE (
		if ( !main_namespace.contains ( clas.toStdString().c_str() ) ) {
		return NULL;
	}
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
	extern void init_game();
}
