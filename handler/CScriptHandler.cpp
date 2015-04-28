#include <QString>
#include "CMap.h"
#include "handler/CHandler.h"
#include "QFile"
#include <QDebug>

CScriptHandler::~CScriptHandler() {
	Py_Finalize();
}

void CScriptHandler::executeScript ( QString script , boost::python::api::object nameSpace ) {
	if ( nameSpace.is_none() ) {
		boost::python::exec ( script.toStdString().append ( "\n" ).c_str(),main_namespace );
	} else {
		boost::python::exec ( script.toStdString().append ( "\n" ).c_str(),nameSpace );
	}
}

QString CScriptHandler::buildCommand ( std::initializer_list<QString> list ) {
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
	return command;
}





void CScriptHandler::executeCommand ( std::initializer_list<QString> list ) {
	executeScript ( buildCommand ( list ) );
}

CScriptHandler::CScriptHandler ( CMap *map ) :QObject ( map ),map ( map ) {
	PyImport_AppendInittab ( "_game",PyInit__game );
	PyImport_AppendInittab ( "_core",PyInit__core );
	Py_Initialize();
	qDebug() <<"Initialized python interpreter."<<"\n";
	main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
	main_namespace=main_module.attr ( "__dict__" );
	boost::python::incref ( main_module.ptr() );
	qDebug() <<"Imported main module."<<"\n";
	executeScript ( CResourcesProvider::getInstance()->getResourceAsString ( "scripts/start.py" ) );
	qDebug() <<"Executed starting scripts."<<"\n";
	CMapScriptLoader *loader=new CMapScriptLoader ( map ) ;
	this->callFunction ( "sys.meta_path.append",boost::ref ( loader ) );
	qDebug() <<"Added loader to meta path"<<"\n";
	this->executeScript ( "import "+map->getMapName() );
	qDebug() <<"Imported map script"<<"\n";
}
