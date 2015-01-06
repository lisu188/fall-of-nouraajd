#include "CScriptLoader.h"
#include "handler/CHandler.h"
#include "CMap.h"
#include <QDebug>

using namespace boost::python;

ModuleSpec::ModuleSpec ( AScriptLoader *loader, std::string name ) :name ( name ) ,scriptLoader ( loader ) {

}

AScriptLoader *ModuleSpec::loader() {
	return scriptLoader;
}

QString CScriptLoader::findModule ( QString modName ) {
	modName=modName.replace ( ".","/" );
	QString modData=CResourcesProvider::getInstance()->getResourceAsString ( "scripts/"+modName+".py" );
	if ( modData=="" ) {
		modData=CResourcesProvider::getInstance()->getResourceAsString ( "scripts/"+modName +"/__init__.py" );
	}
	return modData;
}

QString AScriptLoader::findModule ( std::string modName ) {
	return findModule ( QString::fromStdString ( modName ) );
}

bool AScriptLoader::checkModule ( std::string modName ) {
	return findModule ( modName ) !="";
}

void AScriptLoader::exec_module ( object module ) {
	QString modName=QString::fromStdString ( boost::python::extract<std::string> ( module.attr ( "__name__" ) ) );
	QString modData = findModule ( modName );
	object main_module=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) ) ;
	object main_namespace=main_module.attr ( "__dict__" );
	module.attr ( "__dict__" ) ["__builtins__"]=main_namespace["__builtins__"];
	exec ( modData.toStdString().c_str(),module.attr ( "__dict__" ) );
	qDebug() <<"Loaded module:"<<modName<<"\n";
}

ModuleSpec *AScriptLoader::find_spec ( object name, object, object ) {
	std::string modName=boost::python::extract<std::string> ( name ) ;
	if ( !checkModule ( modName ) ) {
		return nullptr;
	}
	ModuleSpec* spec= new ModuleSpec ( this ,  modName );
	return boost::ref ( spec );
}

AScriptLoader *AScriptLoader::find_module ( boost::python::object name, boost::python::object ) {
	std::string modName=boost::python::extract<std::string> ( name ) ;
	if ( checkModule ( modName ) ) {
		AScriptLoader *loader=this;
		return boost::ref ( loader );
	} else {
		return nullptr;
	}
}

boost::python::object AScriptLoader::load_module ( boost::python::object name ) {
	std::string modName=boost::python::extract<std::string> ( name ) ;
	object sys=boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "sys" ) ) ) ;
	object sysModules=sys.attr ( "modules" );
	if ( sysModules.contains ( name ) ) {
		return sysModules[name];
	}
	boost::python::object module=boost::python::object ( boost::python::handle<> ( PyImport_AddModule ( modName.c_str() ) ) ) ;
	module.attr ( "__name__" ) =name;
	sysModules[name]=module;
	exec_module ( module );
	return module;
}

bool AScriptLoader::checkModule ( QString modName ) {
	return findModule ( modName ) !="";
}

CMapScriptLoader::CMapScriptLoader ( CMap *map ) :map ( map ) {
	this->QObject::setParent ( map );
}

QString CMapScriptLoader::findModule ( QString modName ) {
	if ( modName==map->getMapName() ) {
		return CResourcesProvider::getInstance()->getResourceAsString ( map->getMapPath()+"/script.py" );
	}
	return QString();
}
