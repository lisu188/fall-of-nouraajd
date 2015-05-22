#include "CMap.h"
#include "handler/CHandler.h"
#include "scripting/CScripting.h"
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
    std::shared_ptr<CCustomScriptLoader> loader=std::make_shared<CCustomScriptLoader> ( modName,path );
    callFunction ( "sys.meta_path.append", loader.get()  );
    executeScript ( "import "+modName );
    callFunction ( "sys.meta_path.remove",loader.get() );
}

void CScriptHandler::addFunction ( QString functionName, QString functionCode, std::initializer_list<QString> args ) {
    QString def ( "def "+functionName+"("+QStringList ( args ).join ( "," )+"):" );
    std::stringstream stream;
    stream<<def.toStdString() <<std::endl;
    for ( QString line:functionCode.split ( "\n" ) ) {
        stream<<"\t"<<line.toStdString() <<std::endl;
    }
    executeScript ( QString::fromStdString ( stream.str() ) );
}

void CScriptHandler::import ( QString name ) {
    executeScript ( "import "+name );
}

void CScriptHandler::executeCommand ( std::initializer_list<QString> list ) {
    executeScript ( buildCommand ( list ) );
}


