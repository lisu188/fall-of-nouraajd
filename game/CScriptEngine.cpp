#include "CScriptEngine.h"
#include <QString>
#include "CMap.h"

CScriptEngine::~CScriptEngine() {
	PY_UNSAFE (
	    Py_Finalize(); )
}

CScriptEngine *CScriptEngine::getInstance() {
	static CScriptEngine instance;
	return &instance;
}

void CScriptEngine::executeScript ( QString script ) {
	PY_UNSAFE (
	    boost::python::exec ( script.toStdString().append ( "\n" ).c_str(),main_namespace ); )
}

QString CScriptEngine::buildCommand ( std::initializer_list<QString> list ) {
	PY_UNSAFE (
	    QString command;
	    unsigned int pos = 0;
	for ( auto it = list.begin(); it != list.end(); it++, pos++ ) {
	QString part =   *it ;
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

boost::python::object CScriptEngine::getObject ( QString name ) {
	PY_UNSAFE (
	if ( !main_namespace.contains ( name.toStdString().c_str() ) ) {
	boost::python::object object;
	return object;
}

return main_namespace[name.toStdString().c_str()]; )
}

void CScriptEngine::executeCommand ( std::initializer_list<QString> list ) {
	PY_UNSAFE (
	    executeScript ( buildCommand ( list ) ); )
}

CScriptEngine::CScriptEngine () {
	PY_UNSAFE (
	    PyImport_AppendInittab ( "_game",PyInit__game );
	    Py_Initialize();
	    main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
	    main_namespace=main_module.attr ( "__dict__" );
	    executeScript ( "import sys" );
	    executeScript ( "sys.dont_write_bytecode=True" );
	    executeScript ( "sys.path.append('./scripts')" );
	    executeScript ( "import game" );
	)
}
