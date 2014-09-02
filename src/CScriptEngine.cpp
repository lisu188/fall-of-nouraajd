#include "CScriptEngine.h"
#include <QString>

CScriptEngine::~CScriptEngine() {
	PY_UNSAFE (
	    Py_Finalize(); )
}

void CScriptEngine::executeScript ( QString script ) {
	PY_UNSAFE (
	    boost::python::exec ( script.toStdString().append ( "\n" ).c_str(),main_namespace ); )
}

QString CScriptEngine::buildCommand ( std::initializer_list<std::string> list ) {
	PY_UNSAFE (
	    QString command;
	    int pos = 0;
	for ( auto it = list.begin(); it != list.end(); it++, pos++ ) {
	QString part = ( QString::fromStdString ( *it ) );
		part.replace ( "\"", "\\\"" );
		if ( pos == 0 ) {
			command.append ( part );
			command.append ( "(" );
		} else {
			command.append ( "\"" );
			command.append ( part );
			command.append ( "\"" );
			if ( pos < list.size() - 1 ) {
				command.append ( "," );
			} else {
				command.append ( ")" );
			}
		}
	}
	return command; )
}

boost::python::object CScriptEngine::getObject ( std::string name ) {
	PY_UNSAFE (
	if ( !main_namespace.contains ( name.c_str() ) ) {
	boost::python::object object;
	return object;
}
return main_namespace[name.c_str()]; )
}

void CScriptEngine::executeCommand ( std::initializer_list<std::string> list ) {
	PY_UNSAFE (
	    executeScript ( buildCommand ( list ) ); )
}

CScriptEngine::CScriptEngine ( CMap *map ) {
	PY_UNSAFE (
	    Py_Initialize();
	    init_game();
	    main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
	    main_namespace=main_module.attr ( "__dict__" );
	    executeScript ( "import sys" );
	    executeScript ( "sys.path.append('./scripts')" );
	    executeScript ( "from game import *" ); )
}
