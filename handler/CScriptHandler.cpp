#include "CMap.h"
#include "handler/CHandler.h"

static const char* START_SCRIPT="import sys\n"
                                "from _core import CScriptLoader\n"
                                "sys.path=[]\n"
                                "sys.meta_path.append(CScriptLoader())\n"
                                "sys.dont_write_bytecode=True";

CScriptHandler::CScriptHandler () {
    PyImport_AppendInittab ( "_game",PyInit__game );
    PyImport_AppendInittab ( "_core",PyInit__core );
    Py_Initialize();
    qDebug() <<"Initialized python interpreter."<<"\n";
    main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
    main_namespace=main_module.attr ( "__dict__" );
    boost::python::incref ( main_module.ptr() );
    qDebug() <<"Imported main module."<<"\n";
    executeScript ( START_SCRIPT );
    qDebug() <<"Executed starting scripts."<<"\n";
    for ( QString script:CResourcesProvider::getInstance()->getFiles ( CResType::SCRIPT ) ) {
        executeScript ( "import "+QFileInfo ( script ).baseName() );
    }
}

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

void CScriptHandler::addModule ( QString modName, QString path ) {
    CCustomScriptLoader loader ( modName,path );
    callFunction ( "sys.meta_path.append",boost::ref ( loader ) );
    executeScript ( "import "+modName );
    callFunction ( "sys.meta_path.remove",boost::ref ( loader ) );
}



void CScriptHandler::executeCommand ( std::initializer_list<QString> list ) {
    executeScript ( buildCommand ( list ) );
}


