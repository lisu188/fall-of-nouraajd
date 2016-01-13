#include "CScriptLoader.h"
#include "handler/CHandler.h"

using namespace boost::python;

ModuleSpec::ModuleSpec(std::shared_ptr<AScriptLoader> loader, std::string name) : name(name), script_loader(loader) {

}

std::shared_ptr<AScriptLoader> ModuleSpec::loader() {
    return script_loader;
}

std::string CScriptLoader::find_module(std::string modName) {
    modName = vstd::replace(modName, ".", "/");
    std::string modData = CResourcesProvider::getInstance()->load(vstd::join({"scripts/", modName, ".py"}, ""));
    if (modData == "") {
        modData = CResourcesProvider::getInstance()->load(vstd::join({"scripts/", modName, "/__init__.py"}, ""));
    }
    return modData;
}

CScriptLoader::~CScriptLoader() { }

void AScriptLoader::exec_module(object module) {
    std::string modName = boost::python::extract<std::string>(module.attr("__name__"));
    std::string modData = find_module(modName);
    object main_module = boost::python::object(boost::python::handle<>(PyImport_ImportModule("__main__")));
    object main_namespace = main_module.attr("__dict__");
    module.attr("__dict__")["__builtins__"] = main_namespace["__builtins__"];

    const char *cString = modData.c_str();
    exec(cString, module.attr("__dict__"));
    vstd::logger::debug("Loaded module:", modName, "\n");
}

std::shared_ptr<ModuleSpec> AScriptLoader::find_spec(object name, object, object) {
    std::string modName = boost::python::extract<std::string>(name);
    if (!check_module(modName)) {
        return nullptr;
    }
    return std::make_shared<ModuleSpec>(this->shared_from_this(), modName);
}

bool AScriptLoader::__eq__(boost::python::api::object object) {
    try {
        return boost::python::extract<AScriptLoader *>(object) == this;
    } catch (...) {
        PyErr_Clear();
        return false;
    }
}

AScriptLoader::~AScriptLoader() { }

bool AScriptLoader::check_module(std::string modName) {
    return find_module(modName) != "";
}

CCustomScriptLoader::CCustomScriptLoader(std::string name, std::string path) : name(name), path(path) {

}

std::string CCustomScriptLoader::find_module(std::string modName) {
    if (modName == name) {
        return CResourcesProvider::getInstance()->load(path);
    }
    return std::string();
}

CCustomScriptLoader::~CCustomScriptLoader() { }
