#ifndef SCRIPTMANAGER_H
#define SCRIPTMANAGER_H
#include <QObject>
#include <string>
#include <boost/python.hpp>

class Map;

class ScriptEngine {
public:
	void executeScript ( QString script );
	void executeCommand ( std::initializer_list<std::string> list );
	QString buildCommand ( std::initializer_list<std::string> list );
	boost::python::object getObject ( std::string name );
	ScriptEngine ( Map *map );
	~ScriptEngine();
	template<typename T>
	T createObject ( std::string clas ) {
		try {
			if ( !main_namespace.contains ( clas.c_str() ) ) {
				return NULL;
			}
			std::string script="object=";
			script=script.append ( clas );
			script=script.append ( "()" );
			executeScript ( QString::fromStdString ( script ) );
			executeScript ( "objects.append(object)" );
			return boost::python::extract<T> ( main_namespace["object"] );
		} catch ( ... ) {
			PyErr_Print();
		}
		return NULL;
	}
private:
	boost::python::object main_module;
	boost::python::object main_namespace;
};

#endif // SCRIPTMANAGER_H
