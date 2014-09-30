#include "CLoader.h"
#include "CResourcesHandler.h"

using namespace boost::python;

ModuleSpec::ModuleSpec ( ALoader *loader, std::string name ) :name ( name ) ,scriptLoader ( loader ) {

}

ALoader *ModuleSpec::loader() {
	return scriptLoader;
}

QString CGeneralLoader::findModule ( QString modName ) {
	modName=modName.replace ( ".","/" );
	QString modData=CResourcesHandler::getInstance()->getResourceAsString ( "scripts/"+modName+".py" );
	if ( modData=="" ) {
		modData=CResourcesHandler::getInstance()->getResourceAsString ( "scripts/"+modName +"/__init__.py" );
	}
	return modData;
}

QString ALoader::findModule ( std::string modName ) {
	return findModule ( QString::fromStdString ( modName ) );
}

bool ALoader::checkModule ( std::string modName ) {
	return findModule ( modName ) !="";
}

void ALoader::exec_module ( object module ) {
	QString modName=QString::fromStdString ( boost::python::extract<std::string> ( module.attr ( "__name__" ) ) );
	QString modData = findModule ( modName );
	object main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
	object main_namespace=main_module.attr ( "__dict__" );
	module.attr ( "__dict__" ) ["__builtins__"]=main_namespace["__builtins__"];
	exec ( modData.toStdString().c_str(),module.attr ( "__dict__" ) );
}

ModuleSpec *ALoader::find_spec ( object name, object, object ) {
	std::string modName=boost::python::extract<std::string> ( name ) ;
	if ( !checkModule ( modName ) ) {
		return NULL;
	}
	ModuleSpec* spec= new ModuleSpec ( this ,  modName );
	return boost::ref ( spec );
}


bool ALoader::checkModule ( QString modName ) {
	return findModule ( modName ) !="";
}
