#include "CScriptLoader.h"
#include "handler/CHandler.h"

using namespace boost::python;

ModuleSpec::ModuleSpec ( AScriptLoader *loader, std::string name ) : name ( name ), scriptLoader ( loader ) {

}

AScriptLoader *ModuleSpec::loader() {
    return scriptLoader;
}

std::string CScriptLoader::findModule ( std::string modName ) {
    modName = modName.replace ( ".", "/" );
    std::string modData = CResourcesProvider::getInstance()->load ( "scripts/" + modName + ".py" );
    if ( modData == "" ) {
        modData = CResourcesProvider::getInstance()->load ( "scripts/" + modName + "/__init__.py" );
    }
    return modData;
}

CScriptLoader::~CScriptLoader() { }

std::string AScriptLoader::findModule ( std::string modName ) {
    return findModule ( std::string::fromStdString ( modName ) );
}

bool AScriptLoader::checkModule ( std::string modName ) {
    return findModule ( modName ) != "";
}

void AScriptLoader::exec_module ( object module ) {
    std::string modName = std::string::fromStdString ( boost::python::extract<std::string> ( module.attr ( "__name__" ) ) );
    std::string modData = findModule ( modName );
    object main_module = boost::python::object ( boost::python::handle<> ( PyImport_ImportModule ( "__main__" ) ) );
    object main_namespace = main_module.attr ( "__dict__" );
    module.attr ( "__dict__" ) ["__builtins__"] = main_namespace["__builtins__"];
    QByteArray byteArray = modData.toUtf8();
    const char *cString = byteArray.constData();
    exec ( cString, module.attr ( "__dict__" ) );
    qDebug() << "Loaded module:" << modName << "\n";
}

ModuleSpec *AScriptLoader::find_spec ( object name, object, object ) {
    std::string modName = boost::python::extract<std::string> ( name );
    if ( !checkModule ( modName ) ) {
        return nullptr;
    }
    ModuleSpec *spec = new ModuleSpec ( this, modName );
    return boost::ref ( spec );
}

bool AScriptLoader::__eq__ ( boost::python::api::object object ) {
    try {
        return boost::python::extract<AScriptLoader *> ( object ) == this;
    } catch ( ... ) {
        PyErr_Clear();
        return false;
    }
}

AScriptLoader::~AScriptLoader() { }

bool AScriptLoader::checkModule ( std::string modName ) {
    return findModule ( modName ) != "";
}

CCustomScriptLoader::CCustomScriptLoader ( std::string name, std::string path ) : name ( name ), path ( path ) {

}

std::string CCustomScriptLoader::findModule ( std::string modName ) {
    if ( modName == name ) {
        return CResourcesProvider::getInstance()->load ( path );
    }
    return std::string();
}

CCustomScriptLoader::~CCustomScriptLoader() { }