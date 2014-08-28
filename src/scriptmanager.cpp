#include "scriptmanager.h"
#include "gamescript.h"
#include <QString>
#include <sstream>

ScriptEngine::~ScriptEngine() {
	Py_Finalize();
}

void ScriptEngine::executeScript ( QString script ) {
	boost::python::exec ( script.toStdString().append ( "\n" ).c_str(),main_namespace );
}

QString ScriptEngine::buildCommand ( std::initializer_list<std::string> list ) {
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
	return command;
}

boost::python::object ScriptEngine::getObject ( std::string name ) {
	if ( !main_namespace.contains ( name.c_str() ) ) {
		boost::python::object object;
		return object;
	}
	return main_namespace[name.c_str()];
}

void ScriptEngine::executeCommand ( std::initializer_list<std::string> list ) {
	executeScript ( buildCommand ( list ) );
}

ScriptEngine::ScriptEngine ( Map *map ) {
	Py_Initialize();
	Py_InitModule ( "Game",GameMethods );
	init_Game();
	PyRun_SimpleString ( "import sys" );
	PyRun_SimpleString ( "sys.path.append('./scripts')" );
	PyRun_SimpleString ( "import Game" );
	PyRun_SimpleString ( "from Game import *" );
	PyRun_SimpleString ( "from Objects import *" );
	PyRun_SimpleString ( "from Interactions import *" );
	PyRun_SimpleString ( "objects=[]" );
	std::stringstream stream;
	stream << std::hex << ( unsigned long ) map;
	std::string result ( stream.str() );
	PyObject_SetAttrString ( PyImport_ImportModule ( "__main__" ),"map",Py_BuildValue ( "s",result.c_str() ) );
	main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) );
	main_namespace=main_module.attr ( "__dict__" );
}
