#pragma once

#include "core/CGlobal.h"

class CMap;

class AScriptLoader;

class ModuleSpec {
public:
    ModuleSpec(std::shared_ptr<AScriptLoader> loader, std::string name);

    std::shared_ptr<AScriptLoader> loader();

    std::string name;
    std::string sub_module_search;
    bool has_location = true;
    bool cached = false;
private:
    std::shared_ptr<AScriptLoader> script_loader = 0;
};

class AScriptLoader : public std::enable_shared_from_this<AScriptLoader> {
public:
    virtual std::string find_module(std::string modName) = 0;

    bool check_module(std::string modName);

    void exec_module(boost::python::object module);

    std::shared_ptr<ModuleSpec> find_spec(boost::python::object name, boost::python::object, boost::python::object);

    bool __eq__(boost::python::object object);

    virtual ~AScriptLoader();
};

class CScriptLoader : public AScriptLoader {
public:
    virtual std::string find_module(std::string modName) override;

    virtual ~CScriptLoader();
};

class CCustomScriptLoader : public AScriptLoader {
public:
    CCustomScriptLoader(std::string name, std::string path);

    virtual std::string find_module(std::string modName) override;

    virtual ~CCustomScriptLoader();

private:
    std::string name;
    std::string path;
};


