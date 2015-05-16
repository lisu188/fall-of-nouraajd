#pragma once
#include <QString>
#include <boost/python.hpp>
class CMap;
class AScriptLoader;

class ModuleSpec {
public:
    ModuleSpec ( AScriptLoader *loader,std::string name );
    AScriptLoader *loader();
    std::string name;
    std::string subModuleSearch;
    bool hasLocation=true;
    bool cached=false;
private:
    AScriptLoader *scriptLoader=0;
};

class AScriptLoader {
public:
    virtual QString findModule ( QString modName ) =0;
    QString findModule ( std::string modName );
    bool checkModule ( QString modName );
    bool checkModule ( std::string modName );
    void exec_module ( boost::python::object module );
    ModuleSpec *find_spec ( boost::python::object  name,boost::python::object  ,boost::python::object  );
    bool __eq__ ( boost::python::object object );
};

class CScriptLoader :public AScriptLoader {
public:
    virtual QString findModule ( QString modName ) override;
};

class CCustomScriptLoader :public AScriptLoader {
public:
    CCustomScriptLoader  ( QString name,QString path ) ;
    virtual QString findModule ( QString modName ) override;
private:
    QString name;
    QString path;
};


