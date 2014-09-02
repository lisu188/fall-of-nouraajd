#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <QObject>
#include <string>
#include <boost/python.hpp>
#define PY_UNSAFE(FUNC) try{FUNC}catch(...){PyErr_Print();throw;}

class CMap;

class ScriptEngine {
public:
	void executeScript ( QString script );
	void executeCommand ( std::initializer_list<std::string> list );
	QString buildCommand ( std::initializer_list<std::string> list );
	boost::python::object getObject ( std::string name );
	ScriptEngine ( CMap *map );
	~ScriptEngine();
	template<typename T>
	T createObject ( std::string clas ) {
		PY_UNSAFE (
		if ( !main_namespace.contains ( clas.c_str() ) ) {
		return NULL;
	}
	std::string script="object=";
	                   script=script.append ( clas );
	                   script=script.append ( "()" );
	                   executeScript ( QString::fromStdString ( script ) );
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
#endif // SCRIPTMANAGER_H
